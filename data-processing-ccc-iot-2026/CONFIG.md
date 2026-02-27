# Lambda Configuration Details

This Lambda function is the transformation engine of your architecture. It is automatically triggered whenever new raw data lands in the Bronze bucket. It reads the raw JSON, enriches it by calculating parking availability and splitting date/time fields, and saves the cleaned "business-ready" version into partitioned folders in the Gold bucket. Like the ingestion layer, it operates securely inside your VPC.

### Step 1: Create the Lambda Function & Network Settings

1. Navigate to the **AWS Lambda Console** and click **Create function**.
2. Select **Author from scratch**.
3. **Function name:** `data-processing-ccc-iot-2026`
4. **Runtime:** Python 3.14.
5. **Architecture:** x86_64.
6. Under **Permissions**, expand *Change default execution role*, select **Use an existing role**, and choose your **`LabRole`** from the dropdown.
7. Expand the **Advanced settings** section at the bottom of the page:
* Check the box for **Enable VPC**.
* **VPC:** Select your `parking-ccc-iot-2026-vpc`.
* **Subnets:** Select your **Private Subnet** (e.g., `parking-ccc-iot-2026-subnet-private1` and `parking-ccc-iot-2026-subnet-private2`).
* **Security groups:** Select your **`lambda-s3-only-sg`** (ensuring this function is strictly locked down to AWS services).


8. Click **Create function**.

### Step 2: Configure Environment Variables

You need to tell your code where to drop the transformed, enriched data.

1. Go to the **Configuration** tab, then select **Environment variables** on the left menu.
2. Click **Edit** and add a new variable:
* **Key:** `GOLD_BUCKET_NAME`
* **Value:** The exact name of your S3 Gold bucket (e.g., `gold-bucket-ccc-iot-2026`).
* **Key:** `LOT_PHYSICAL_CAPACITY`
* **Value:** The exact name of your S3 Gold bucket (e.g., `14`).
* **Key:** `SPOTS_UNDER_REPAIR`
* **Value:** The exact name of your S3 Gold bucket (e.g., `2`).


3. Click **Save**.

### Step 3: Increase Execution Timeout

Because this function parses JSON data, performs calculations, and writes to a new S3 bucket, it needs more than the default 3 seconds to run reliably.

1. Go to the **Configuration** tab.
2. Select **General configuration** from the left-hand menu.
3. Click **Edit**.
4. Change the **Timeout** to **1 min 0 sec**.
5. Click **Save**.

### Step 4: Verify IAM Permissions (`LabRole`)

Your function needs the power to read the raw files from Bronze (`s3:GetObject`) and write the clean files to Gold (`s3:PutObject`).

1. Go to **Configuration > Permissions**.
2. Ensure the **Execution Role** is set to **`LabRole`**. If it isn't, click **Edit** and switch it.

### Step 5: Add the S3 Trigger

You need to tell the Bronze bucket to wake this function up the instant a new file is uploaded.

1. Go to your **Lambda function overview** at the top of the page.
2. Click **+ Add trigger**.
3. Select **S3** from the dropdown menu.
4. **Bucket:** Select your **Bronze Bucket** (e.g., `raw-bucket-ccc-iot-2026`).
5. **Event type:** Select **All object create events**.
6. Check the box to acknowledge the recursive invocation warning and click **Add**.

> **⚠️ Important Architecture Note:** Never set an S3 trigger to output data to the *same* bucket it is reading from! Doing so creates an infinite loop (Lambda writes a file, which triggers the Lambda, which writes a file...) that can drain your AWS credits in minutes. **Always read from Bronze, write to Gold!**

### Step 6: Set Reserved Concurrency (Lab Limit Protection)

Just like the ingestion function, we must cap this function so it doesn't accidentally consume all your lab resources during a high-traffic event.

1. Go to the **Configuration** tab, then select **Concurrency** on the left menu.
2. Click **Edit** under Reserved concurrency.
3. Set the **Reserved concurrency** to **3**.
4. Click **Save**.