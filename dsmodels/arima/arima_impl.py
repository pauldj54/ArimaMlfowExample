import itertools
import logging
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from statsmodels import api as sm
from sklearn.utils.validation import check_array, column_or_1d
from dsmodels.exception.arima_exception import ArimaException
from statsmodels.tsa.statespace.sarimax import SARIMAXResults

from mlflow import log_metric, log_param, log_artifact, sklearn
import mlflow

import uuid

from verta import Client
import verta

class ARIMA():
    """
    Parameters
    p: The order of the autoregressive model
    d: The degree of differencing
    q: The order of the moving average model
    trend: str or iterable, optional (default='c')
    start_params: array-like, optional (default=None)
    method: str, one of {'css-mle','mle','css'}, optional (default=None)
    """

    def __init__(self, q, d, p, trend, start_params, method):
        logging.info("Initialising ARIMA object")
        self.p = p
        self.q = q
        self.d = d

        self.trend = trend

        self.start_params = start_params #array-like, optional (default=None)
        self.method = method
        self.results = []
        self.param = []
        self.param_season = []
        self.AIC = []
        self.sarimax_model = []
        self.run=None

        self.__init_plot()


    def __init_plot(self):
        plt.rcParams['figure.figsize'] = (20.0, 10.0)
        plt.rcParams.update({'font.size': 12})
        plt.style.use('ggplot')

    def __pdq_iterations(self):
        """
        Private function to generate all the combinations for p d q
        :return: List
        """
        return list(itertools.product(self.p, self.d, self.q))

    def __seasonal_pdq(self):
        """
        Private function to return all seasonal combinations
        :return:
        """
        return [(x[0], x[1], x[2], 12) for x in self.pdq_list]

    def __generate_pkl_filename(self,path,filename,version):
        return path+filename+version+'.pkl'

    def save_model(self, results):

        """
        This function will allow you to save a SARIMAX model to a pickle file

        :param results: MLEResults ( the result of calling the fit function on SARIMAX)
        :return: None
        """
        #mlflow.sklearn.log_model(results,"sarmiax")
        self.run.log_model(results)




    def load_model(self,path,filename,version):
        """

        :param path: Full or relative path for the model file
        :param filename: Name of the file
        :param version: Version number
        :return: unpickled instance of the SARIMAX model
        """
        return SARIMAXResults.load(self.__generate_pkl_filename(path, filename, version))
        mlflow.sklearn.load_model()

    def fit(self, train_data):
        """
        Fit function on an ARIMA model.
        :param train_data: Panda dataseries
        :return: Nothing
        """
        #mlflow.tracking.set_tracking_uri("http://yves-alb-dev-767301589.eu-central-1.elb.amazonaws.com/")
        #mlflow.tracking.set_tracking_uri("http://localhost:5000/")
        client = Client("http://localhost:3000")
        proj = client.set_project("My first ARIMA ModelDB project")
        expt = client.set_experiment("YYC Experiment 3 Save model")
        run = client.set_experiment_run("First Run")


        self.run = run
        number_iterations=0
        logging.info("Generate the parameter grid")
        self.pdq_list = self.__pdq_iterations()

        run.log_dataset("train_data", train_data, overwrite=True)

        fit_iterations=[]
        aic_results=[]
        for param in self.pdq_list:
            for param_season in self.__seasonal_pdq():
                try:
                    number_iterations = number_iterations + 1
                    print("the param season {}".format(str(param_season)))
                    #tuples are not supported
                    #run.log_hyperparameters({"seasonal_pdq1_"+str(number_iterations) : param_season[0]})
                    #run.log_hyperparameters({"seasonal_pdq2_" + str(number_iterations): param_season[1]})
                    #run.log_hyperparameters({"seasonal_pdq3_" + str(number_iterations): param_season[2]})
                    #run.log_hyperparameters({"seasonal_pdq4_" + str(number_iterations): param_season[3]})

                    fit_iterations.append(number_iterations)

                    results = self.train(train_data=train_data, param=param, param_season=param_season)
                    logging.info("Training success")
                    self.AIC.append(results.aic)
                    self.sarimax_model.append([param, param_season])
                    run.log_observation("aic",results.aic)
                    #run.log_metric("aic_"+str(number_iterations),results.aic)
                    aic_results.append(results.aic)
                except ArimaException:
                    logging.error("A fatal issue occurred during the training")
        #Because of the boolean value in the proto function only attributes support key - list combo
        #run.log_metric("aic",aic_results)
        #run.log_metric("fit_iterations",fit_iterations)
        run.log_attribute("aic",aic_results)
        run.log_attribute("fit_iterations", fit_iterations)
        run.log_observation()
        #mlflow.end_run()


    def plot_arima_results(self,results):
        results.plot_diagnostics(figsize=(20, 14))
        plt.show()


    def train(self, train_data, param, param_season):
        """
        Function to train the arima model for a given endog, order and seasonal order.
        :param train_data: The data as a pandas series
        :param param: The (p,d,q) order of the model for the number of AR parameters, differences, and MA parameters
        :param param_season: The (P,D,Q,s) order of the seasonal component of the model for the AR parameters, differences, MA parameters, and periodicity
        :return: Akaike Information Criterion
        """

        try:
            mod = sm.tsa.statespace.SARIMAX(endog=train_data,
                                            order=param,
                                            seasonal_order=param_season,
                                            enforce_stationarity=False,
                                            enforce_invertibility=False)
            results = mod.fit(disp=False)
            return results
        except:
            raise ArimaException

    def validate_array(self,array_values,ensure_2d):
        """
        Ravel column or 1d numpy array, else raises an error

        :param array_values:
        :param ensure2D:
        :return: Returns a 1dim numpy array or throws error when fails
        """
        return column_or_1d(check_array(array_values, ensure_2d, force_all_finite=False, copy=False, dtype=None))