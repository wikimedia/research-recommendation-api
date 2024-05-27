# Load testing with locust

We are using [locust](https://locust.io/) to perform load testing. Below are the steps to set up a load test environment, run load tests, store and compare the results of previous load test.

## 1. Environment Setup:
Run the commands below to set up a testing environment on `stat1008`:
```
$ python3 -m venv load_test_venv
$ source load_test_venv/bin/activate
$ pip install -r requirements.txt
```
We use `stat1008` to maintain consistency in our testing environment. This ensures that the results are comparable across different test runs and minimizes variations due to environmental factors.

## 2. Run Load Tests & Print Results:
Run the locust CLI in [headless](https://docs.locust.io/en/stable/quickstart.html#direct-command-line-usage-headless) mode:
```
locust
```
This command will run the locust load test using `locust.conf` and `locustfile.py`, store and compare the results of the previous load test, then print the results in the console.

## 3. Next Steps:
Locust creates multiple CSV files to store load test results. These files are not required for subsequent tests except for `liftwing_load_tests_history.csv`. You can delete the unnecessary files using the command below before adding changes to the repository:
```
rm !(liftwing_load_tests_history).csv
```
