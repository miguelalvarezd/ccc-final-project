# ATHENA SETUP

Before we can type our first SQL command, there is one notorious "AWS Gotcha" we have to handle: **Athena will refuse to run any queries until you tell it where to save the results.** Looking back at the Lambda script you shared earlier, you already created a bucket for this: `s3://temporal-athena-ccc-iot-2026/athena-results/`. Let's configure Athena to use it.

### Step 1: Set Up the Query Results Location

1. Open the **Athena Console** in AWS.
2. Click on **Query editor** on the left-hand menu.
3. You will likely see a blue banner at the top saying you need to set up a query result location. Click the **Edit settings** button in that banner (or click the **Settings** tab near the top right, then click **Manage**).
4. In the **Location of query result** box, paste your bucket path:
`s3://temporal-athena-ccc-iot-2026/athena-results/`
5. Click **Save**.

### Step 2: Select Your Database

1. Go back to the **Editor** tab.
2. On the left side, under the **Data** panel, find the **Database** dropdown.
3. Select **`iot_data`** (the database your Glue Crawler just built).
4. Under the **Tables** section below it, you should see the table the Crawler generated (e.g., `gold_bucket...`).

### Step 3: Run Your First Test Query

Let's make sure everything is connected properly and the data is readable for your historical logs.

1. In the main query window (Query 1), paste this simple command (replace `your_table_name` with the exact name you see on the left):

```sql
SELECT * FROM "iot_data"."your_table_name"
LIMIT 10;

```

2. Click the blue **Run** button.
3. Scroll down to the **Results** section. You should see a beautiful table containing all your JSON fields (`device_id`, `status`, `event_date`, `lot_usable_spaces`, etc.), cleanly organized into columns!

### Step 4: The "Real World" Business Query

To fulfill your project's goal of allowing parking operators to monetize real-time availability, let's run the query we discussed earlier that finds the *exact current status* of every spot in the lot right now.

Open a new query tab (the `+` icon) and run this:

```sql
SELECT sensor_id, status, event_time, lot_usable_spaces
FROM (
    SELECT *, 
           row_number() OVER (PARTITION BY sensor_id ORDER BY event_timestamp DESC) as row_num
    FROM "iot_data"."your_table_name"
)
WHERE row_num = 1
ORDER BY sensor_id;

```

*This query groups your data by the sensor, sorts it so the newest event is at the top (`row_num = 1`), and filters out all the older history.*

If everything comes back green and you can see your data, your entire backend pipeline (from Edge to Athena) is officially fully functional!