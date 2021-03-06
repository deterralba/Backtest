from source.Backtest import *
from mpl_toolkits.mplot3d import Axes3D
from scipy import interpolate
import numpy as np
from matplotlib.widgets import Slider, RadioButtons
from os import listdir, makedirs


# STRATEGIES

class JMTendanceStrat(Strategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def new_day(self):
        for the_asset in self.market.assetList:
            data = self.market.get_asset_data(the_asset)
            if len(data) > 2:
                if data[-1] > data[-2] > data[-3]:
                    self.market.open(self.portfolio, the_asset, 5, "LONG")
                elif data[-1] < data[-2] < data[-3]:
                    for position in self.portfolio.openPositionList:
                        self.market.close(position)


class JMTestStrat(Strategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def new_day(self):
        the_asset = self.market.assetList[0]
        if self.market.theDay == 0:
            self.market.open(self.portfolio, the_asset, 1, "LONG")
        if self.market.theDay == 1:
            self.market.close(self.portfolio.openPositionList[0])
            self.market.open(self.portfolio, the_asset, 1, "LONG")
        if self.market.theDay == 5:
            self.market.close(self.portfolio.openPositionList[0])


class JMMobileStrategy(Strategy):
    def __init__(self, *args, **kwargs):
        temp_kwargs = kwargs.copy()
        del kwargs["longMedian"]
        del kwargs["shortMedian"]
        if "asset" in kwargs:
            del kwargs["asset"]

        if "typeOfPred" in kwargs:
            del kwargs["typeOfPred"]
            self.typeOfPred = temp_kwargs["typeOfPred"]
        else:
            self.typeOfPred = "UP"

        self.longMedian = temp_kwargs["longMedian"]
        self.shortMedian = temp_kwargs["shortMedian"]

        super().__init__(*args, **kwargs)

        self.pastShortSum = []
        self.pastLongSum = []
        self.initialised = False

        if "asset" in temp_kwargs and temp_kwargs["asset"] is not None:
            self.asset = temp_kwargs["asset"]
        else:
            self.asset = self.market.assetList[0]

    def new_day(self):
        """ Called each day by the market to ask the expert to make its predictions """
        if self.initialised:
            data = self.market.get_asset_data(self.asset)

            short_sum = self.pastShortSum[-1]
            long_sum = self.pastLongSum[-1]

            short_sum += data[-1] / self.shortMedian  # -1 because i start at 0
            short_sum -= data[-1 - self.shortMedian] / self.shortMedian  # -1 because i start at 0
            long_sum += data[-1] / self.longMedian  # -1 because i start at 0
            long_sum -= data[-1 - self.longMedian] / self.longMedian  # -1 because i start at 0

            # it's important to close the prediction before opening the new ones
            # UP: if short go under long, we close the previously opened position
            if short_sum < long_sum and self.pastLongSum[-1] < self.pastShortSum[-1] and "UP" in self.typeOfPred:
                if len(self.portfolio.openPositionList) > 0:
                    self.market.close(self.portfolio.openPositionList[0])
            # DOWN: if short go above long, we close the previously opened position
            if short_sum > long_sum and self.pastLongSum[-1] > self.pastShortSum[-1] and "DOWN" in self.typeOfPred:
                if len(self.portfolio.openPositionList) > 0:
                    self.market.close(self.portfolio.openPositionList[0])

            # UP: if short go above long, we open a position
            if short_sum > long_sum and self.pastLongSum[-1] > self.pastShortSum[-1] and "UP" in self.typeOfPred:
                self.market.open(self.portfolio, self.asset, 1/data[-1], "LONG")
            # DOWN: if short go under long, we open a position
            if short_sum < long_sum and self.pastLongSum[-1] < self.pastShortSum[-1] and "DOWN" in self.typeOfPred:
                self.market.open(self.portfolio, self.asset, 1/data[-1], "LONG")

            self.pastLongSum.append(long_sum)
            self.pastShortSum.append(short_sum)

        # if it is the first time self.market.theDay > self.longMedian, the median value are initialised
        elif self.market.theDay >= self.longMedian - 1:
            self.initialised = True
            data = self.market.get_asset_data(self.asset)
            # print("data sent", data, self.market.theDay)
            short_sum = 0
            long_sum = 0
            for i in range(self.longMedian):
                # print(-i-1)
                long_sum += data[-i - 1]  # -1 because i start at 0
            long_sum /= self.longMedian
            for i in range(self.shortMedian):
                short_sum += data[-i - 1]  # -1 because i start at 0
            short_sum /= self.shortMedian
            self.pastLongSum.append(long_sum)
            self.pastShortSum.append(short_sum)

    def plot_medians(self, offset=0):
        size = min(len(self.pastShortSum) + self.longMedian - 1, len(self.asset.data))
        x = list(range(size))
        translation_list = [None] * (self.longMedian - 1)
        translated_short = translation_list + self.pastShortSum
        translated_long = translation_list + self.pastLongSum

        # print(len(translated_short), len(translated_long), len(x))

        plt.plot(x, translated_short, label="Short Median")
        plt.plot(x, translated_long, label="Long Median")
        plt.plot(x, self.asset.data[:size], label=self.asset.name)

        openDayList = [position.openTrade.day - offset for position in self.portfolio.closePositionList]
        closeDayList = [position.closeTrade.day - offset for position in self.portfolio.closePositionList]
        plt.plot(openDayList, [2]*len(openDayList), 'go')
        plt.plot(closeDayList, [4]*len(closeDayList), 'ro')
        plt.title("Warning, points true only if first_day = 0")


        plt.legend(loc=2)
        plt.show(block=True)

    def __repr__(self):
        return "<{0}, long: {1}, short: {2}>".format(self.name, self.longMedian, self.shortMedian)


# EXPERTS

class JMTendanceExpert(Expert):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def new_day(self):
        """ Called each day by the market to ask the expert to make its predictions """
        pred = ["UP", "DOWN"]
        for the_asset in self.market.assetList:
            data = self.market.get_asset_data(the_asset)
            if len(data) > 2:
                if data[-1] > data[-2] > data[-3]:
                    Prediction(the_asset, pred[1], self.market.theDay + 1,
                               self, self.market.theDay, self.market)
                elif data[-1] < data[-2] < data[-3]:
                    Prediction(the_asset, pred[0], self.market.theDay + 1,
                               self, self.market.theDay, self.market)


class JMMobileExpert(Expert):
    def __init__(self, *args, **kwargs):
        # TODO end the implementation of "predictionTerm" in the test_the_ME
        temp_kwargs = kwargs.copy()
        del kwargs["longMedian"]
        del kwargs["shortMedian"]
        if "asset" in kwargs:
            del kwargs["asset"]

        if "predictionTerm" in kwargs:
            del kwargs["predictionTerm"]
            self.predictionTerm = temp_kwargs["predictionTerm"]
        else:
            self.predictionTerm = math.floor((temp_kwargs["shortMedian"] + temp_kwargs["longMedian"]) / 2)

        if "typeOfPred" in kwargs:
            del kwargs["typeOfPred"]
            self.typeOfPred = temp_kwargs["typeOfPred"]
        else:
            self.typeOfPred = "UPDOWN"

        self.longMedian = temp_kwargs["longMedian"]
        self.shortMedian = temp_kwargs["shortMedian"]

        super().__init__(*args, **kwargs)

        self.pastShortSum = []
        self.pastLongSum = []
        self.initialised = False

        if "asset" in temp_kwargs and temp_kwargs["asset"] is not None:
            self.asset = temp_kwargs["asset"]
        else:
            self.asset = self.market.assetList[0]

    def new_day(self):
        """ Called each day by the market to ask the expert to make its predictions """
        if self.initialised:
            data = self.market.get_asset_data(self.asset)

            # old methode, unefficient
            # short_sum = 0
            # long_sum = 0
            # for i in range(self.longMedian):
            #     long_sum += data[-i - 1]  # -1 because i start at 0
            # long_sum /= self.longMedian
            # for i in range(self.shortMedian):
            #     short_sum += data[-i - 1]  # -1 because i start at 0
            # short_sum /= self.shortMedian

            short_sum = self.pastShortSum[-1]
            long_sum = self.pastLongSum[-1]

            short_sum += data[-1] / self.shortMedian  # -1 because i start at 0
            short_sum -= data[-1 - self.shortMedian] / self.shortMedian  # -1 because i start at 0
            long_sum += data[-1] / self.longMedian  # -1 because i start at 0
            long_sum -= data[-1 - self.longMedian] / self.longMedian  # -1 because i start at 0

            pred = ["UP", "DOWN"]
            if short_sum > long_sum and self.pastLongSum[-1] > self.pastShortSum[-1] and "UP" in self.typeOfPred:
                Prediction(self.asset, pred[0], self.market.theDay + self.predictionTerm,
                           self, self.market.theDay, self.market)
            if short_sum < long_sum and self.pastLongSum[-1] < self.pastShortSum[-1] and "DOWN" in self.typeOfPred:
                Prediction(self.asset, pred[1], self.market.theDay + self.predictionTerm,
                           self, self.market.theDay, self.market)

            self.pastLongSum.append(long_sum)
            self.pastShortSum.append(short_sum)

        # if it is the first time self.market.theDay > self.longMedian, the median value are initialised
        elif self.market.theDay >= self.longMedian - 1:
            self.initialised = True
            data = self.market.get_asset_data(self.asset)
            # print("data sent", data, self.market.theDay)
            short_sum = 0
            long_sum = 0
            for i in range(self.longMedian):
                # print(-i-1)
                long_sum += data[-i - 1]  # -1 because i start at 0
            long_sum /= self.longMedian
            for i in range(self.shortMedian):
                short_sum += data[-i - 1]  # -1 because i start at 0
            short_sum /= self.shortMedian
            self.pastLongSum.append(long_sum)
            self.pastShortSum.append(short_sum)

    def plot_medians(self):
        size = min(len(self.pastShortSum) + self.longMedian - 1, len(self.asset.data))
        x = list(range(size))
        translation_list = [None] * (self.longMedian - 1)
        translated_short = translation_list + self.pastShortSum
        translated_long = translation_list + self.pastLongSum

        # print(len(translated_short), len(translated_long), len(x))

        plt.plot(x, translated_short, label="Short Median")
        plt.plot(x, translated_long, label="Long Median")
        plt.plot(x, self.asset.data[:size], label=self.asset.name)
        plt.legend(loc=2)
        plt.show(block=True)

    def __repr__(self):
        return "<{0}, long: {1}, short: {2}>".format(self.name, self.longMedian, self.shortMedian)


class JMRandomExpert(Expert):
    def __init__(self, *args, **kwargs):
        temp_kwargs = kwargs.copy()
        if "asset" in kwargs:
            del kwargs["asset"]

        if "predictionTerm" in kwargs:
            del kwargs["predictionTerm"]
            self.predictionTerm = temp_kwargs["predictionTerm"]
        else:
            self.predictionTerm = 1

        if "numberOfPredictions" in kwargs:
            del kwargs["numberOfPredictions"]

        if "first_day" in kwargs:
            del kwargs["first_day"]

        if "last_day" in kwargs:
            del kwargs["last_day"]

        if "typeOfPred" in kwargs:
            del kwargs["typeOfPred"]
            self.typeOfPred = temp_kwargs["typeOfPred"]
        else:
            self.typeOfPred = "UP"

        super().__init__(*args, **kwargs)

        if "asset" in temp_kwargs and temp_kwargs["asset"] is not None:  # is after super() because needs self.market
            self.asset = temp_kwargs["asset"]
        else:
            self.asset = self.market.assetList[0]

        self.daysOfPrediction = []
        if "numberOfPredictions" in temp_kwargs:
            first_day = 0
            last_day = self.market.maximumDay
            if "first_day" in temp_kwargs and temp_kwargs["first_day"] is not None:
                first_day = temp_kwargs["first_day"]
            if "last_day" in temp_kwargs and temp_kwargs["last_day"] is not None:
                last_day = temp_kwargs["last_day"]
            # print("Random :", first_day, last_day)

            for i in range(temp_kwargs["numberOfPredictions"]):
                # randint(a, b) include b, maximumDay starts at 0
                self.daysOfPrediction.append(random.randint(first_day, last_day - self.predictionTerm))
            self.daysOfPrediction.sort()
        else:
            print("!!! WRONG numberOfPredictions FOR JMRandomExpert !!!")

    def new_day(self):
        """ Called each day by the market to ask the expert to make its predictions """
        while self.market.theDay in self.daysOfPrediction :
            pred = ["UP", "DOWN"]
            if self.typeOfPred == "UPDOWN":
                typeOfPred = pred[random.randint(0, 1)]
                # print(typeOfPred)
            else:
                typeOfPred = self.typeOfPred

            self.daysOfPrediction.remove(self.market.theDay)  # only remove the first instance in the list
            Prediction(self.asset, typeOfPred, self.market.theDay + self.predictionTerm,
                       self, self.market.theDay, self.market)

    def __repr__(self):
        return "<{0}>".format(self.name)


# SIMULATION FUNCTION V1

def test_the_mobile_expert(number_of_line, number_of_column, first_day, last_day, print_time=True):
    """ Return the matrix where M(i, j) is the expected value of an MobileExpert which parameters are
    longMedain = j+1, shortMedia = i+1, simulated from first_day to last_day """

    beginning_time = clock()  # for time execution measurement
    matrix_of_results = np.zeros((number_of_line, number_of_column))
    for i in range(number_of_line):  # short median
        # print(i, (clock() - beginning_time), "s")
        for j in range(number_of_column):  # long median
            if j > i:
                JMMobile = JMMobileExpert(theBacktest.market, "MobileExpert", longMedian=j + 1, shortMedian=i + 1)
                theBacktest.simule(first_day=first_day, last_day=last_day, string_mode=False)
                theBacktest.soft_reset()
                matrix_of_results[i, j] = JMMobile.results_description()[4]
            else:
                matrix_of_results[i, j] = 0.5
    if print_time:
        print((clock() - beginning_time), "s")
    return matrix_of_results


def super_test_the_mobile_expert(number_of_line, number_of_column, windows_duration, first_day, last_day,
                                 print_time=True, **kwargs):
    """  last_day is excluded """
    if "windows_offset" in kwargs:
        windows_offset = kwargs["windows_offset"]
    else:
        windows_offset = windows_duration

    length_of_the_asset = last_day - first_day
    last_day = windows_duration + first_day

    number_of_windows = int((length_of_the_asset - windows_duration) / windows_offset)

    list_of_results = []

    beginning_time = clock()  # for time execution measurement
    for i in range(number_of_windows + 1):
        list_of_results.append(
            test_the_mobile_expert(number_of_line, number_of_column, first_day, last_day, print_time=False))
        print(first_day, last_day, (clock() - beginning_time), "s")
        first_day += windows_offset
        last_day += windows_offset

    return list_of_results


def plot_the_mobile_expert(number_of_line, number_of_column, matrix_of_results, plot_type="3D"):
    if plot_type == "3D":
        X = np.arange(0, number_of_line)
        Y = np.arange(0, number_of_column)

        # X, Y = np.meshgrid(X, Y)  # old command, does not work if number_of_column != number_of_line
        X, Y = np.mgrid[0:number_of_line, 0:number_of_column]
        # print(X, Y, "\n", matrix_of_results)
        fig = plt.figure()

        ax = fig.add_subplot(111, projection='3d')  # fig.gca(projection='3d')
        surf = ax.plot_surface(X, Y, matrix_of_results, rstride=1, cstride=1, cmap=plt.cm.RdYlGn, linewidth=0,
                               antialiased=True)

        # # to add a new part in the graph NB localisation problem needs to be solved
        # ax2 = fig.add_subplot(211, projection='3d')
        # surf2 = ax2.plot_surface(Y, X, matrix_of_results, rstride=1, cstride=1, cmap=plt.cm.RdYlGn, linewidth=0, antialiased=True)

        # this is the cloud of points
        # ax.scatter(X, Y, Z)

        ax.set_zlim(0, 1)
        fig.colorbar(surf, shrink=0.7, aspect=10)

        alpha_axis = plt.axes([0.25, 0.15, 0.65, 0.03])
        alpha_slider = Slider(alpha_axis, 'Amp', 0, 1, valinit=.5)
        alpha_slider.on_changed(lambda val: update(ax, val))

        def update(ax, val):
            alpha = alpha_slider.val
            ax.cla()
            plt.draw()

        plt.show()

    if plot_type == "2D":
        # # supersimple method
        # plt.matshow(matrix_of_results)
        # plt.show(block=True)

        # fig = plt.figure()  # seems useless here
        # ax = fig.add_subplot()  # seems useless here
        plt.imshow(matrix_of_results, cmap=plt.cm.RdYlGn, interpolation="nearest")
        plt.colorbar()
        # plt.plot()  # seems useless here
        plt.show(block=True)


def plot_several_matrix(number_of_line, number_of_column, list_of_results, plot_type="3D", interpolation="nearest"):
    # the min and max of the list of matrix are searched to set the scale
    list_of_max = []
    list_of_min = []
    for matrix in list_of_results:
        list_of_max.append(matrix.max())
        list_of_min.append(matrix.min())
    max_of_results = max(list_of_max)
    min_of_results = min(list_of_min)

    # use for the slider
    val_max = 1 / len(list_of_results)

    if plot_type == "2D":
        def update(ax, val):
            index = min(int(val / val_max), len(list_of_results) - 1)
            # print(val, index)
            ax.cla()
            image = ax.imshow(list_of_results[index], cmap=plt.cm.RdYlGn, interpolation=interpolation)
            image.set_clim([min_of_results, max_of_results])
            # plt.draw()

        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        fig.subplots_adjust(left=0.25, bottom=0.25)
        image = ax1.imshow(list_of_results[0], cmap=plt.cm.RdYlGn, interpolation=interpolation)
        image.set_clim([min_of_results, max_of_results])
        plt.colorbar(image)
        alpha_axis = plt.axes([0.25, 0.15, 0.65, 0.03])
        alpha_slider = Slider(alpha_axis, 'First day', 0, 1, valinit=0)
        alpha_slider.on_changed((lambda val: update(ax1, val)))

        plt.show(block=True)

    if plot_type == "2D+":

        def update(ax, val):
            index = min(int(val / val_max), len(list_of_results) - 1)
            # print(val, index)
            ax.cla()
            image1 = ax.imshow(list_of_results[index], cmap=plt.cm.RdYlGn, interpolation=interpolation)
            image1.set_clim([min_of_results, max_of_results])
            # plt.draw()

        def radiofunc(label):
            if label == "variance":
                image = ax2.imshow(variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                image.set_clim([0, variance.max()])
                colorbar2.update_bruteforce(image)
                # colorbar2 = fig.colorbar(image, ax=ax2)
            if label == "expectation":
                image = ax2.imshow(esperance, cmap=plt.cm.RdYlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            if label == "EV  - VAR":
                image = ax2.imshow(esperance - variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            if label == "EV + VAR":
                image = ax2.imshow(esperance + variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            plt.draw()


        esperance = sum(list_of_results) / len(list_of_results)

        variance = np.zeros((number_of_line, number_of_column))
        for i in range(number_of_line):
            for j in range(number_of_column):
                if j > i:
                    list_of_elem = []
                    for matrix in list_of_results:
                        list_of_elem.append(matrix[i, j])
                    variance[i, j] = statistics.stdev(list_of_elem)

        fig = plt.figure()
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        fig.subplots_adjust(left=0.25, bottom=0.25)
        image1 = ax1.imshow(list_of_results[0], cmap=plt.cm.RdYlGn, interpolation=interpolation)
        image1.set_clim([min_of_results, max_of_results])

        image = ax2.imshow(esperance, cmap=plt.cm.RdYlGn, interpolation=interpolation)
        ax2.set_xlabel("Long Median")
        ax2.set_ylabel("Short Median")
        colorbar1 = fig.colorbar(image1, ax=ax1)
        colorbar2 = fig.colorbar(image, ax=ax2)

        alpha_axis = plt.axes([0.15, 0.12, 0.5, 0.05])
        alpha_slider = Slider(alpha_axis, 'First day', 0, 1, valinit=0)
        alpha_slider.on_changed((lambda val: update(ax1, val)))

        rax = plt.axes([0.75, 0.1, 0.2, 0.1])  # rect = [left, bottom, width, height]
        radio = RadioButtons(rax, ("variance", "expectation", "EV  - VAR", "EV + VAR"), active=1)
        radio.on_clicked(radiofunc)

        fig.subplots_adjust(left=0.1, bottom=0.25)
        plt.show(block=True)
        plt.show(block=True)

    if plot_type == "3D":
        def update(ax, val):
            index = min(int(val / val_max), len(list_of_results) - 1)
            ax.cla()
            surf = ax.plot_surface(X, Y, list_of_results[index], rstride=1, cstride=1,
                                   cmap=plt.cm.RdYlGn, linewidth=0, antialiased=True)
            ax.set_zlim(min_of_results, max_of_results)
            surf.set_clim([min_of_results, max_of_results])
            # plt.draw()


        X = np.arange(0, number_of_line)
        Y = np.arange(0, number_of_column)
        X, Y = np.mgrid[0:number_of_line, 0:number_of_column]

        fig = plt.figure()
        ax1 = fig.add_subplot(111, projection='3d')
        fig.subplots_adjust(left=0.25, bottom=0.25)

        surf = ax1.plot_surface(X, Y, list_of_results[0], rstride=1, cstride=1,
                                cmap=plt.cm.RdYlGn, linewidth=0, antialiased=True)
        ax1.set_zlim(min_of_results, max_of_results)
        fig.colorbar(surf, shrink=0.7, aspect=10)

        surf.set_clim([min_of_results, max_of_results])
        alpha_axis = plt.axes([0.25, 0.15, 0.65, 0.03])
        alpha_slider = Slider(alpha_axis, 'First day', 0, 1, valinit=0)
        alpha_slider.on_changed((lambda val: update(ax1, val)))

        plt.show(block=True)

    if plot_type == "3D+":

        def update(ax, val):
            index = min(int(val / val_max), len(list_of_results) - 1)
            # print(val, index)
            ax.cla()
            surf = ax.plot_surface(X, Y, list_of_results[index], rstride=1, cstride=1,
                                   cmap=plt.cm.RdYlGn, linewidth=0.2, antialiased=True)
            ax.set_zlim(min_of_results, max_of_results)
            surf.set_clim([min_of_results, max_of_results])
            # plt.draw()

        def radiofunc(label):
            if label == "variance":
                image = ax2.imshow(variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                image.set_clim([0, variance.max()])
                colorbar2.update_bruteforce(image)
                # colorbar2 = fig.colorbar(image, ax=ax2)
            if label == "expectation":
                image = ax2.imshow(esperance, cmap=plt.cm.RdYlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            if label == "EV  - VAR":
                image = ax2.imshow(esperance - variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            if label == "EV + VAR":
                image = ax2.imshow(esperance + variance, cmap=plt.cm.YlGn, interpolation=interpolation)
                # image.set_clim([min_of_results, max_of_results])
                colorbar2.update_bruteforce(image)
            plt.draw()

        X = np.arange(0, number_of_line)
        Y = np.arange(0, number_of_column)
        X, Y = np.mgrid[0:number_of_line, 0:number_of_column]

        fig = plt.figure()
        ax1 = fig.add_subplot(121, projection='3d')
        ax2 = fig.add_subplot(122)

        esperance = sum(list_of_results) / len(list_of_results)

        variance = np.zeros((number_of_line, number_of_column))
        for i in range(number_of_line):
            for j in range(number_of_column):
                if j > i:
                    list_of_elem = []
                    for matrix in list_of_results:
                        list_of_elem.append(matrix[i, j])
                    variance[i, j] = statistics.stdev(list_of_elem)

        surf = ax1.plot_surface(X, Y, list_of_results[0], rstride=1, cstride=1,
                                cmap=plt.cm.RdYlGn, linewidth=0.2, antialiased=True)
        surf.set_clim([min_of_results, max_of_results])
        ax1.set_zlim(min_of_results, max_of_results)

        image = ax2.imshow(esperance, cmap=plt.cm.RdYlGn, interpolation=interpolation)
        ax2.set_xlabel("Long Median")
        ax2.set_ylabel("Short Median")
        colorbar1 = fig.colorbar(surf, ax=ax1)
        colorbar2 = fig.colorbar(image, ax=ax2)

        alpha_axis = plt.axes([0.15, 0.12, 0.5, 0.05])
        alpha_slider = Slider(alpha_axis, 'First day', 0, 1, valinit=0)
        alpha_slider.on_changed((lambda val: update(ax1, val)))

        rax = plt.axes([0.75, 0.1, 0.2, 0.1])  # rect = [left, bottom, width, height]
        radio = RadioButtons(rax, ("variance", "expectation", "EV  - VAR", "EV + VAR"), active=1)
        radio.on_clicked(radiofunc)

        fig.subplots_adjust(left=0.1, bottom=0.25)
        plt.show(block=True)


# SIMULATION FUNCTION V2

def write_a_prediction_list_on_file(file_name, prediction_list, format_type=0, overwrite=True, first_line=None):
    """ Receive a prediction list and write a csv with the results, depending of the format """
    data = []
    if format_type == 0:  # [long, short, day, isTrue]       without asset
        for prediction in prediction_list:
            data.append([prediction.expert.longMedian, prediction.expert.shortMedian,
                         prediction.day, prediction.isTrue])

    if format_type == 1:  # [long, short, asset, day, isTrue]
        for prediction in prediction_list:
            data.append([prediction.expert.longMedian, prediction.expert.shortMedian,
                         prediction.asset.name, prediction.day, prediction.isTrue])

    if format_type == 2:  # [long, short, asset, mean of all the prediction, number of prediction]
        mean = [prediction.isTrue for prediction in prediction_list].count(True)/len(prediction_list)
        data.append([prediction_list[0].expert.longMedian, prediction_list[0].expert.shortMedian,
                     prediction_list[0].asset.name, mean, len(prediction_list)])

    if format_type == 3:  # [long, short, list of the results (size varies)] or [predictionTerm, nbOfPred, ... for Rand
        if len(prediction_list) > 0:
            # for list taken from experts
            if isinstance(prediction_list[0], Prediction):
                if isinstance(prediction_list[0].expert, JMMobileExpert):
                    temp_list = [prediction_list[0].expert.longMedian, prediction_list[0].expert.shortMedian]
                elif isinstance(prediction_list[0].expert, JMRandomExpert):
                    temp_list = [prediction_list[0].expert.predictionTerm, len(prediction_list)]
            # for list taken from strategies
            elif isinstance(prediction_list[0], Position):
                temp_list = [prediction_list[0].portfolio.name, len(prediction_list)]
            else:
                print("!!! WRONG EXPERT FOR format_type = 3 !!! Type:", type(prediction_list[0]))
                return
            temp_list += [prediction.result for prediction in prediction_list]
            data.append(temp_list)
            # print(data)
        else:
            temp_list = ["NO PREDICTION", "FOR THIS COUPLE"]
            data.append(temp_list)

    if format_type == 4:  # [long, short, length of the position (size varies)] FOR POSITION (strategies)
        if len(prediction_list) > 0:
            if isinstance(prediction_list[0], Position):
                temp_list = [prediction_list[0].portfolio.name, len(prediction_list)]
            else:
                print("!!! WRONG EXPERT FOR format_type = 4 !!! Type:", type(prediction_list[0]))
                return
            temp_list += [position.closeTrade.day - position.openTrade.day for position in prediction_list]
            data.append(temp_list)
            # print(data)
        else:
            temp_list = ["NO POSITION", "FOR THIS COUPLE"]
            data.append(temp_list)

    data_writer(file_name, data, overwrite=overwrite, first_line=first_line)


def test_and_write_several_experts(list_of_medians, file_name,
                                   print_time=True, overwrite=True, format_type=3, asset=None, randomReference=True,
                                   typeOfPred="UP", random_file_name="default_random_file.csv",
                                   numberOfRandPredictions=200, first_day=None, last_day=None,
                                   prediction_term_type="median"):
    """  """
    if overwrite:
        data_writer(file_name, [])
        if randomReference:
            data_writer(random_file_name, [])

    beginning_time = clock()  # for time execution measurement
    i, j = 0, 0

    for couple in list_of_medians:
        if prediction_term_type == "short":
            temp_prediction_term = couple[1]
        elif prediction_term_type == "long":
            temp_prediction_term = couple[0]
        elif prediction_term_type == "median":
            temp_prediction_term = math.floor((couple[0] + couple[1])/2)
        else:
            print("!!! WRONG predictionTerm IN test_and_write_several_experts, set to 1 !!!")
            temp_prediction_term = 1

        the_expert = JMMobileExpert(theBacktest.market, "MobileExpert",
                                    longMedian=couple[0], shortMedian=couple[1], asset=asset, typeOfPred=typeOfPred,
                                    predictionTerm=temp_prediction_term)
        if randomReference:
            the_rand_expert = JMRandomExpert(theBacktest.market, "RandomExpert",  asset=asset,
                                             numberOfPredictions=numberOfRandPredictions, predictionTerm=temp_prediction_term,
                                             typeOfPred=typeOfPred, first_day=first_day, last_day=last_day)

        theBacktest.simule(string_mode=False, first_day=first_day, last_day=last_day)

        write_a_prediction_list_on_file(file_name, the_expert.predictionMadeList,
                                        format_type=format_type, overwrite=False)
        if randomReference:
            write_a_prediction_list_on_file(random_file_name, the_rand_expert.predictionMadeList,
                                            format_type=format_type, overwrite=False)
            if len(the_rand_expert.predictionMadeList) != numberOfRandPredictions:
                print("!!! WRONG PREDICTION MADE LIST SIZE : ", len(the_rand_expert.predictionMadeList), " !!!")

        if print_time:
            i += 1
            j += 1
            if i == 100:
                i = 0
                remaining_time = (clock()-beginning_time)*(len(list_of_medians)-j)/j
                print("{:.1f}% done, still {:.1f}s for".format(100*j/len(list_of_medians), remaining_time),
                      the_expert.asset.name)
        theBacktest.soft_reset()
    if print_time:
        print("End of {} in {:.1f}s with the prediction type '{}'".format(asset.name, clock() - beginning_time,
                                                                          prediction_term_type))

def do_a_full_expert_simulation(assetDirectory, nameOfTheSimulation, numberOfStep, typeOfPred, prediction_term_type, short_simulation=False):

    print("******************** Beggining of the 'do_a_full_expert_simulation' ********************")

    # the max day needs to be reinitialised
    theBacktest.hard_reset()

    nameList = []  # 'human' name of the assets
    fileList = []  # path file of the assets
    realFileNameNoExtension = []  # path file of the results
    assetList = []  # list of Asset objects
    rawFileList = listdir(assetDirectory)

    # debug mode
    # rawFileList = [rawFileList[0]]
    #

    for name in rawFileList:
        temp_name = name.split('-')
        nameList.append(temp_name[0])
    fileList = [assetDirectory + file for file in rawFileList]
    for file in zip(fileList, nameList):  # powerful function ! fusion list elem by elem
        assetList.append(theBacktest.add_asset_from_csv(file[0], "yahoo",  ",", file[1]))

    # for asset in assetList:
    #     theBacktest.market.plot_market(asset)

    resultsDirectory = "Results/"
    realDirectory = resultsDirectory + nameOfTheSimulation + "/real/"
    randomDirectory = resultsDirectory + nameOfTheSimulation + "/random/"

    makedirs(resultsDirectory + nameOfTheSimulation, exist_ok=True)
    makedirs(realDirectory, exist_ok=True)
    makedirs(randomDirectory, exist_ok=True)

    filePrefix = ""  # prefix for the serie of results files created by the simulation
    randomFileSuffix = "_rand"  # prefix for the serie of results files created by the simulation
    realFileNameNoExtension = [realDirectory + filePrefix + name for name in nameList]
    randomFileNameNoExtension = [randomDirectory + filePrefix + name + randomFileSuffix for name in nameList]


    list_of_medians = []
    for i in range(20, 75, 4):
        for j in range(10, i-7, 2):
            list_of_medians.append([i, j])
    print(len(list_of_medians))
    if not short_simulation:
        for i in range(75, 150, 4):
            for j in range(10, i-10, 2):
                list_of_medians.append([i, j])
        print(len(list_of_medians))
        for i in range(150, 250, 5):
            for j in range(10, i-40, 5):
                list_of_medians.append([i, j])
    print("Number of couples tested:", len(list_of_medians))

    # print(list_of_medians)
    # plt.plot(*zip(*list_of_medians), marker='x', color='b', ls='')
    # plt.show()

    nomberOfDays = min([asset.length for asset in assetList])
    numberOfDaysInStep = math.floor(nomberOfDays/numberOfStep)
    # print(nomberOfDays, numberOfStep, numberOfDaysInStep*numberOfStep)
    all_beginning_time = clock()  # for time execution measurement
    for i in range(numberOfStep):
        first_day = numberOfDaysInStep*i
        last_day = numberOfDaysInStep*(i+1)-1
        print("=============== STEP {}/{} ===============".format(i+1, numberOfStep))
        print("         day {} -> {}".format(first_day, last_day))
        beginning_time = clock()  # for time execution measurement
        realFileName = [file + "_{}.csv".format(i+1) for file in realFileNameNoExtension]
        randomFileName = [file + "_{}.csv".format(i+1) for file in randomFileNameNoExtension]
        # print(randomFileName, realFileName)

        for file in zip(assetList, realFileName, randomFileName):
            test_and_write_several_experts(list_of_medians, file[1],
                                           print_time=True, overwrite=True,
                                           format_type=3, asset=file[0], randomReference=True,
                                           random_file_name=file[2], numberOfRandPredictions=200,
                                           first_day=first_day, last_day=last_day,
                                           typeOfPred=typeOfPred, prediction_term_type=prediction_term_type)
        print("--- Step done in {:.1f}s, still {:.1f}s ---".format(clock()-beginning_time,
                                                                  (clock()-all_beginning_time)/(i+1)*(numberOfStep-i-1)))

    first_line = "this simulation was made with the following " \
                 "medians in {:.1f}s in {} steps and {} prediction with a {} term:".format(clock() - all_beginning_time,
                                                                                           numberOfStep, typeOfPred,
                                                                                           prediction_term_type)

    data_writer(resultsDirectory + nameOfTheSimulation + "/" + filePrefix + "readme.txt", list_of_medians,
                first_line=first_line)

    print(first_line, "- median not printed (too long)")
    print("******************** End of the 'do_a_full_expert_simulation' ********************\n")

def test_and_write_several_MAstrategies(list_of_medians, file_name, print_time=True, overwrite=True,
                                        format_type=3, asset=None, randomReference=True,
                                        typeOfPred="UP", random_file_name="default_random_file.csv",
                                        numberOfRandPredictions=200, first_day=None, last_day=None):
    """  """
    if overwrite:
        data_writer(file_name, [])
        if randomReference:
            data_writer(random_file_name, [])

    beginning_time = clock()  # for time execution measurement
    i, j = 0, 0

    for couple in list_of_medians:
        the_strategy = JMMobileStrategy(theBacktest.market, "MobileExpert-{}-{}".format(couple[0], couple[1]),
                                        longMedian=couple[0], shortMedian=couple[1], asset=asset, typeOfPred=typeOfPred)

        # NB here we have a reference that has a prediction_term fixed !
        if randomReference:
            the_rand_expert = JMRandomExpert(theBacktest.market, "RandomExpert",  asset=asset,
                                             numberOfPredictions=numberOfRandPredictions, predictionTerm=50,
                                             typeOfPred=typeOfPred, first_day=first_day, last_day=last_day)

        theBacktest.simule(string_mode=False, first_day=first_day, last_day=last_day)
        # the_strategy.plot_medians()

        write_a_prediction_list_on_file(file_name, the_strategy.portfolio.closePositionList,
                                        format_type=format_type, overwrite=False)
        if randomReference:
            write_a_prediction_list_on_file(random_file_name, the_rand_expert.predictionMadeList,
                                            format_type=format_type, overwrite=False)
            if len(the_rand_expert.predictionMadeList) != numberOfRandPredictions:
                print("!!! WRONG PREDICTION MADE LIST SIZE : ", len(the_rand_expert.predictionMadeList), " !!!")

        if print_time:
            i += 1
            j += 1
            if i == 100:
                i = 0
                remaining_time = (clock()-beginning_time)*(len(list_of_medians)-j)/j
                print("{:.1f}% done, still {:.1f}s for".format(100*j/len(list_of_medians), remaining_time),
                      the_strategy.asset.name)
        theBacktest.soft_reset()
    if print_time:
        print("End of {} in {:.1f}s by the MAStrategy".format(the_strategy.asset.name, clock() - beginning_time))

def do_a_full_strategy_simulation(assetDirectory, nameOfTheSimulation, numberOfStep, typeOfPred, short_simulation=False):

    print("******************** Beggining of the 'do_a_full_strategy_simulation' ********************")

    # the max day needs to be reinitialised
    theBacktest.hard_reset()

    nameList = []  # 'human' name of the assets
    fileList = []  # path file of the assets
    realFileNameNoExtension = []  # path file of the results
    assetList = []  # list of Asset objects
    rawFileList = listdir(assetDirectory)

    # debug mode
    # rawFileList = [rawFileList[0]]
    #


    for name in rawFileList:
        temp_name = name.split('-')
        nameList.append(temp_name[0])
    fileList = [assetDirectory + file for file in rawFileList]
    for file in zip(fileList, nameList):  # powerful function ! fusion list elem by elem
        assetList.append(theBacktest.add_asset_from_csv(file[0], "yahoo",  ",", file[1]))

    # for asset in assetList:
    #     theBacktest.market.plot_market(asset)

    resultsDirectory = "Results/"
    realDirectory = resultsDirectory + nameOfTheSimulation + "/real/"
    randomDirectory = resultsDirectory + nameOfTheSimulation + "/random/"

    makedirs(resultsDirectory + nameOfTheSimulation, exist_ok=True)
    makedirs(realDirectory, exist_ok=True)
    makedirs(randomDirectory, exist_ok=True)

    filePrefix = ""  # prefix for the serie of results files created by the simulation
    randomFileSuffix = "_rand"  # prefix for the serie of results files created by the simulation
    realFileNameNoExtension = [realDirectory + filePrefix + name for name in nameList]
    randomFileNameNoExtension = [randomDirectory + filePrefix + name + randomFileSuffix for name in nameList]


    list_of_medians = []
    for i in range(20, 75, 4):
        for j in range(10, i-7, 2):
            list_of_medians.append([i, j])
    print(len(list_of_medians))
    if not short_simulation:
        for i in range(75, 150, 4):
            for j in range(10, i-10, 2):
                list_of_medians.append([i, j])
        print(len(list_of_medians))
        for i in range(150, 250, 5):
            for j in range(10, i-40, 5):
                list_of_medians.append([i, j])
    print("Number of couples tested:", len(list_of_medians))

    # print(list_of_medians)
    # plt.plot(*zip(*list_of_medians), marker='x', color='b', ls='')
    # plt.show()

    nomberOfDays = min([asset.length for asset in assetList])
    numberOfDaysInStep = math.floor(nomberOfDays/numberOfStep)
    # print(nomberOfDays, numberOfStep, numberOfDaysInStep*numberOfStep)
    all_beginning_time = clock()  # for time execution measurement
    for i in range(numberOfStep):
        first_day = numberOfDaysInStep*i
        last_day = numberOfDaysInStep*(i+1)-1
        print("=============== STEP {}/{} ===============".format(i+1, numberOfStep))
        print("         day {} -> {}".format(first_day, last_day))
        beginning_time = clock()  # for time execution measurement
        realFileName = [file + "_{}.csv".format(i+1) for file in realFileNameNoExtension]
        randomFileName = [file + "_{}.csv".format(i+1) for file in randomFileNameNoExtension]
        # print(randomFileName, realFileName)

        for file in zip(assetList, realFileName, randomFileName):
           test_and_write_several_MAstrategies(list_of_medians, file[1],
                                               print_time=True, overwrite=True,
                                               format_type=3, asset=file[0], randomReference=True,
                                               random_file_name=file[2], numberOfRandPredictions=200,
                                               first_day=first_day, last_day=last_day,
                                               typeOfPred=typeOfPred)
        print("--- Step done in {:.1f}s, still {:.1f}s ---".format(clock()-beginning_time,
                                                                  (clock()-all_beginning_time)/(i+1)*(numberOfStep-i-1)))

    first_line = "this simulation was made with the following " \
                 "medians in {:.1f}s in {} steps and {}".format(clock() - all_beginning_time, numberOfStep, typeOfPred)

    data_writer(resultsDirectory + nameOfTheSimulation + "/" + filePrefix + "readme.txt", list_of_medians,
                first_line=first_line)

    print(first_line, "- median not printed (too long)")
    print("******************** End of the 'do_a_full_strategy_simulation' ********************\n")

# MAIN !

if __name__ == "__main__":
    # An instance of Backtest is created
    theBacktest = Backtest()

    # ---------------------------------------------------------- #
    # ----------------- SIMULATION FUNCTION V2 ----------------- #
    # ---------------------------------------------------------- #

    # assetDirectory = "Data/MAdata00/"  # example: "Data/MAdata00/"
    # nameOfTheSimulation = "S3_down_short_00"
    # numberOfStep = 4
    # typeOfPred = "DOWN"  # can be UP DOWN UPDOWN
    # prediction_term_type = "short"  # can be short long median
    #
    # do_a_full_expert_simulation(assetDirectory, nameOfTheSimulation, numberOfStep, typeOfPred, prediction_term_type):

    # do_a_full_expert_simulation("Data/MAdata00/", "S5_down_long_00", 4, "DOWN", "long")
    # do_a_full_expert_simulation("Data/MAdata00/", "S5_up_long_00", 4, "UP", "long")
    # do_a_full_expert_simulation("Data/MAdata00/", "S5_down_short_00", 4, "DOWN", "short")
    # do_a_full_expert_simulation("Data/MAdata00/", "S5_up_short_00", 4, "UP", "short")
    # do_a_full_expert_simulation("Data/MAdata00/", "S5_down_median_00", 4, "DOWN", "median")
    # do_a_full_expert_simulation("Data/MAdata00/", "S5_up_median_00", 4, "UP", "median")
    #
    # do_a_full_strategy_simulation("Data/MAdata00/", "S5_up_fullstrat_00", 4, "UP")
    # do_a_full_strategy_simulation("Data/MAdata00/", "S5_down_fullstrat_00", 4, "DOWN")


    do_a_full_strategy_simulation("Data/MAdata95/", "S5_up_fullstrat_95", 4, "UP")
    do_a_full_strategy_simulation("Data/MAdata95/", "S5_down_fullstrat_95", 4, "DOWN")

    do_a_full_expert_simulation("Data/MAdata95/", "S5_down_long_95", 4, "DOWN", "long")
    do_a_full_expert_simulation("Data/MAdata95/", "S5_up_long_95", 4, "UP", "long")
    do_a_full_expert_simulation("Data/MAdata95/", "S5_down_short_95", 4, "DOWN", "short")
    do_a_full_expert_simulation("Data/MAdata95/", "S5_up_short_95", 4, "UP", "short")
    do_a_full_expert_simulation("Data/MAdata95/", "S5_down_median_95", 4, "DOWN", "median")
    do_a_full_expert_simulation("Data/MAdata95/", "S5_up_median_95", 4, "UP", "median")


    # do_a_full_strategy_simulation("Data/MAdata00/", "S4_down_short_00", 4, "DOWN", short_simulation=True)

    # ---------------------------------------------------------- #
    # -------------- END : SIMULATION FUNCTION V2 -------------- #
    # ---------------------------------------------------------- #





    # ---------------------------------------------------------- #
    # ------------------- MANUAL SIMULATION -------------------- #
    # ---------------------------------------------------------- #

    # Assets are added to the Backtest
    # DENTS = theBacktest.add_asset_from_csv("Data/uniformtest.csv", "propre", ";", "DENTS")
    # STUP = theBacktest.add_asset_from_csv("Data/stupidtest.csv", "propre", ";", "STUP")
    # BTCUSD = theBacktest.add_asset_from_csv("Data/BTCUSD_propre.csv", "propre", ";", "BTCUSD")
    # IBM = theBacktest.add_asset_from_csv("Data/ibm_propre.csv", "propre", ";", "IBM")
    # GS = theBacktest.add_asset_from_csv("Data/GS_yahoo.csv", "yahoo", ",", "GS")
    # IGE = theBacktest.add_asset_from_csv("Data/IGE_yahoo.csv", "yahoo", ",", "IGE")
    # SPY = theBacktest.add_asset_from_csv("Data/SPY_yahoo.csv", "yahoo", ",", "SPY")
    # IBMyahoo = theBacktest.add_asset_from_csv("Data/IBM_1970_2010_yahoo.csv", "yahoo", ",", "IBM")
    # aapl = theBacktest.add_asset_from_csv("Data/MAdata95/aapl-03.01.95.csv", "yahoo", ",", "AAPL")
    # msft = theBacktest.add_asset_from_csv("Data/MAdata95/msft-03.01.95.csv", "yahoo", ",", "MSFT")



    # beginning_time = clock()  # for time execution measurement
    # for file in zip(assetList, realFileName, randomFileName):
    #     test_and_write_several_experts(list_of_medians, file[1],
    #                                    print_time=True, overwrite=True,
    #                                    format_type=3, asset=file[0], randomReference=True,
    #                                    random_file_name=file[2], numberOfRandPredictions=200)
    #
    # first_line = "this simulation was made with the following medians in {}s :".format(clock() - beginning_time)
    # data_writer(resultsDirectory + filePrefix + "readme.txt", list_of_medians, first_line=first_line)

    # randomStrategy = Strategy(theBacktest.market, "Random Srategy", cash=15000)
    # JMMAStrategy = JMMobileStrategy(theBacktest.market, "Mobile Srategy",
    #                                 cash=15000, longMedian=20, shortMedian=10, typeOfPred="DOWN")
    # JMstrat = JMTendanceStrat(theBacktest.market, "StupidDetector", cash=15000)
    # firstDayStrat = FirstDayBuyEverythingStrategy(theBacktest.market, "BuyTheFirstDay", asset=aapl, cash=15000)
    # JMstratTest = JMTestStrat(theBacktest.market, "TestStrat", cash=15000)

    # Experts are created
    # absurdExpert = Expert(theBacktest.market, "AbsurdExpert")
    # TendanceExpert = JMTendanceExpert(theBacktest.market, "TendanceExpert")
    # MobileExpert = JMMobileExpert(theBacktest.market, "MobileExpert", longMedian=20, shortMedian=10, typeOfPred="DOWN")
    # RandomExpert = JMRandomExpert(theBacktest.market, "RandomExpert",
    #                               numberOfPredictions=2, predictionTerm=18, typeOfPred="UP")
    #
    # theBacktest.simule(string_mode=True)
    # print([position.result for position in randomStrategy.portfolio.closePositionList])
    # print([position.closeTrade.day - position.openTrade.day for position in JMMAStrategy.portfolio.closePositionList])
    # write_a_prediction_list_on_file("Results/test.csv", JMMAStrategy.portfolio.closePositionList,
    #                                 format_type=3, overwrite=True, first_line=None)

    # test_and_write_several_MAstrategies([[45,20],[150,30],[80,23]], "Results/test.csv", print_time=True, overwrite=True,
    #                                     format_type=3, asset=None, randomReference=True,
    #                                     typeOfPred="UPDOWN", random_file_name="Results/test_rand.csv",
    #                                     numberOfRandPredictions=200, first_day=None, last_day=None)
    # print(len(JMstrat.portfolio.closePositionList))
    # MobileExpert.plot_medians()
    # JMMAStrategy.plot_medians()

    # theBacktest.soft_reset()

    # ---------------------------------------------------------- #
    # ----------------- END: MANUAL SIMULATION ----------------- #
    # ---------------------------------------------------------- #




    # ---------------------------------------------------------- #
    # ----------------- SIMULATION FUNCTION V1 ----------------- #
    # ---------------------------------------------------------- #

    # print(test_the_mobile_expert(3, 3, 0, 500, print_time=True))

    # beginning_time = clock()  # for time execution measurement
    # number_of_line = 55  # short median
    # number_of_column = 55  # long median
    # matrix_of_results = test_the_mobile_expert(number_of_line, number_of_column, 0, 1000)
    #
    # windows_duration = 800
    # first_day = 0
    # last_day = 1600
    # list_of_results = super_test_the_mobile_expert(number_of_line, number_of_column,
    #                                                windows_duration, first_day, last_day,
    #                                                windows_offset=400, print_time=True)

    # for i in range(len(list_of_results)):
    # plot_the_mobile_expert(number_of_line, number_of_column, list_of_results[i], plot_type="3D")
    # plot_several_matrix(number_of_line, number_of_column, list_of_results, plot_type="3D+", interpolation="nearest")

    # ---------------------------------------------------------- #
    # -------------- END : SIMULATION FUNCTION V1 -------------- #
    # ---------------------------------------------------------- #



    # may be useful part of code
    # We plot the assets used
    # theBacktest.market.plot_market()

    # theBacktest.simule(string_mode=True)
    # theBacktest.simule(first_day=0, last_day=500, string_mode=True)
    # MobileExpert.plot_medians()