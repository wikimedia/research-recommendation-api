import os
import pandas as pd
from datetime import datetime
from locust import between, events, FastHttpUser, task


@events.test_stop.add_listener
def liftwing_load_tests_history(**kwargs):
    """
    Event listener for Locust test_stop event to log load test results following the workflow below:
    1. Read the summary statistics from "rec_api_ng_stats.csv".
    2. Filter the rows to get only the GET requests summary.
    3. Add the current timestamp to the summary row.
    4. Check if "liftwing_load_tests_history.csv" exists:
       - If not, create the file and write the summary row with a header.
       - If yes, append the summary row to the existing file without a header.
    5. Print a message about the completion of the first load test if the file is newly created.
    6. Call the `liftwing_load_tests_analysis()` function to analyze the results if the file already exists.
    """
    df = pd.read_csv("rec_api_ng_stats.csv")
    get_requests_summary_row = df[df["Type"] == "GET"]
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    get_requests_summary_row.insert(0, "Timestamp", current_time)

    if not os.path.isfile("liftwing_load_tests_history.csv"):
        get_requests_summary_row.to_csv(
            "liftwing_load_tests_history.csv", mode="w", index=False
        )
        first_report = """
        LIFTWING LOAD TEST COMPLETED
        The first load test for this isvc has been successfully executed and recorded.
        At present, a comparative analysis is not available due to the absence of preceding test data.
        Future tests will enable us to present a comparative performance analysis.
        For load test results, please refer to: liftwing_load_tests_history.csv.
        """
        print(first_report)
    else:
        get_requests_summary_row.to_csv(
            "liftwing_load_tests_history.csv", mode="a", index=False, header=False
        )
        liftwing_load_tests_analysis()


def liftwing_load_tests_analysis():
    """
    Analyze the most recent load test results and compare them with the previous test following the workflow below:
    1. Read the historical load test data from the liftwing_load_tests_history.csv file.
    2. Sort the data by the "Timestamp" column.
    3. Extract the last two rows for comparison.
    4. Calculate the percentage change for the specified columns.
    5. Store the percentage change values in a new DataFrame.
    6. Check if any percentage change exceeds the 10% threshold and generate a corresponding analysis message.
    7. Print a detailed report of the analysis.
    """
    percentage_threshold = 10
    df = pd.read_csv("liftwing_load_tests_history.csv")
    df = df.sort_values(by=["Timestamp"], ascending=True)
    # Compare %age change in: Average Response Time, Median Response Time, Requests/s
    columns_to_compare = ["Average Response Time", "Median Response Time", "Requests/s"]
    last_two_rows = df.tail(2)
    # Create a new DataFrame to store percentage change values
    percentage_change_df = pd.DataFrame(
        columns=[f"{column} Change %" for column in columns_to_compare]
    )
    for column in columns_to_compare:
        # Get the values of the last two rows for the current column
        last_value = last_two_rows.iloc[-1][column]
        second_last_value = last_two_rows.iloc[-2][column]
        # Calculate percentage change
        percentage_change = ((last_value - second_last_value) / second_last_value) * 100
        # Append percentage change to the new DataFrame
        percentage_change_df.loc[0, f"{column} Change %"] = percentage_change

    # Check if any column has a percentage change above 10% threshold and print the columns and their values
    performance_is_worse = False
    analysis_data = ""

    if percentage_change_df.gt(percentage_threshold).any().any():
        performance_is_worse = True
        analysis_data += "Columns with percentage change above 10:\n"
        for column in percentage_change_df.columns:
            if percentage_change_df[column].iloc[0] > percentage_threshold:
                analysis_data += (
                    f"\t{column}: {percentage_change_df[column].iloc[0]:.2f}%\n"
                )
    else:
        analysis_data += f"Columns {columns_to_compare} have changes below {percentage_threshold}% threshold.\n"

    performance, difference = (
        ("worse", "regression") if performance_is_worse else ("better", "improvement")
    )
    analysis_report = """
        LIFTWING LOAD TEST COMPLETED
        The most recent load test for this isvc has been analyzed and presents {difference} in performance:
        {analysis_data}
        Compared with the prior load test, the performance is {performance}.
        Detailed results of the current and past load tests are located in: liftwing_load_tests_history.csv.
        """.format(
        performance=performance, difference=difference, analysis_data=analysis_data
    )
    print(analysis_report)


class RecommendationAPILiftWing(FastHttpUser):
    """
    Load test simulation for the Recommendation API hosted on LiftWing.

    This class simulates a user making requests to the recommendation API
    with specific query parameters, mimicking the following curl request:
    curl -s "https://api.wikimedia.org/service/lw/recommendation/v1/api?s=en&t=fr&n=3&article=Apple"
    """

    wait_time = between(1, 2)  # Adjust wait time as needed
    host = "https://api.wikimedia.org"

    @task
    def predict(self):
        """
        Task to send a GET request to the recommendation API.
        """
        params = {"s": "en", "t": "fr", "n": "3", "article": "Apple"}
        self.client.get("/service/lw/recommendation/v1/api", params=params)
