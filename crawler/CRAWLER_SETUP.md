# CRAWLER SETUP

A Crawler's job is to act like a scout. It will automatically read those nested `year=2026/month=02/day=23/` folders in your Gold bucket, figure out the schema (all your JSON fields like `event_date` and `lot_available_spaces`), and build a table for Athena to query.

Looking back at the Athena Data Querying Lambda script you shared earlier, I noticed you set `DATABASE = "iot_data"` and `TABLE = "gold_data"`. We will set up the Glue Crawler to match those exact names so your script works perfectly!

Here is the step-by-step guide to setting it up in your lab environment:

### Step 1: Create the Database

First, we need to create the database container where the Crawler will put the table.

1. Open the **AWS Glue Console**.
2. On the left-hand menu, under **Data Catalog**, click on **Databases**.
3. Click the **Add database** button.
4. Name the database exactly **`iot_data`** (this matches your Lambda script).
5. Click **Create database**.

### Step 2: Create and Configure the Crawler

1. On the left-hand menu, under **Data Catalog**, click on **Crawlers**.
2. Click the **Create crawler** button.
3. **Name:** Give it a name like `gold_bucket_crawler` and click Next.
4. **Choose data sources:** * Click **Add a data source**.
* Data source: **S3**
* S3 path: Click the **Browse** button and select your Gold bucket (e.g., `s3://gold-bucket-ccc-iot-2026/`). *Note: Make sure to select the root of the bucket, not a specific day's folder!*
* Subsequent crawler runs: **Crawl all sub-folders**
* Click **Add an S3 data source**, then click Next.


5. **Configure security (IAM Role):**
* Under IAM role, choose **Use an existing IAM role**.
* From the dropdown, select your trusty **`LabRole`** (since it already has all the S3 permissions we need!). Click Next.


6. **Set output and scheduling:**
* Target database: Select the **`iot_data`** database you just created.
* Table name prefix: Leave this blank.
* Crawler schedule: Set frequency to **On demand** (for this project, you can just run it manually when you want to update Athena).
* Click Next.


7. Review your settings and click **Create crawler**.

### Step 3: Run the Crawler!

1. You should now be back on the Crawlers page. Select your new `gold_bucket_crawler`.
2. Click the **Run crawler** button at the top right.
3. The status will change to *Running*, then *Stopping*, and finally back to *Ready*. (This usually takes about 1 to 2 minutes).

### Step 4: Verify the Table

Once it finishes running, check to see what it built:

1. On the left menu, under **Data Catalog**, click **Tables**.
2. You should see a new table! Glue usually names the table after the S3 bucket (e.g., `gold-bucket-ccc-iot-2026`).

**Crucial detail for your Lambda script:** If Glue named your table `gold_bucket_ccc_iot_2026`, you just need to go back to your **Data Querying Lambda** script and change line 12 to match it exactly:
`TABLE = "gold_bucket_ccc_iot_2026"`