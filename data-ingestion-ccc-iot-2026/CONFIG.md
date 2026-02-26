# Lambda Configuration Details

This Lambda function acts as the bridge between your SQS queue and your S3 Bronze bucket. It pulls the raw IoT messages from the queue and saves them as JSON files in S3. Because it is placed inside your secure VPC, it uses your NAT Gateway and VPC Endpoints to safely move data without exposing it to the public internet.

### Step 1: Create the Lambda Function & Network Settings

1. Navigate to the **AWS Lambda Console** and click **Create function**.
2. Select **Author from scratch**.
3. **Function name:** `data-ingestion-ccc-iot-2026`
4. **Runtime:** Python 3.14.
5. **Architecture:** x86_64.
6. Under **Permissions**, expand *Change default execution role*, select **Use an existing role**, and choose your **`LabRole`** from the dropdown.
7. Expand the **Advanced settings** section at the bottom of the page:
* Check the box for **Enable VPC**.
* **VPC:** Select your `parking-ccc-iot-2026-vpc`.
* **Subnets:** Select your **Private Subnet** (e.g., `parking-ccc-iot-2026-subnet-private1` and `parking-ccc-iot-2026-subnet-private2`). *Never put backend Lambdas in the public subnet!*
* **Security groups:** Select your **`lambda-s3-only-sg`** (to enforce the principle of least privilege, ensuring this function can only talk to AWS services).


8. Click **Create function**. *(Note: It may take an extra minute to create because AWS is attaching the network interfaces to your VPC).*

### Step 2: Configure Environment Variables

You need to tell your code exactly where to drop the raw data.

1. Go to the **Configuration** tab, then select **Environment variables** on the left menu.
2. Click **Edit** and add a new variable:
* **Key:** `BRONZE_BUCKET_NAME`
* **Value:** The exact name of your S3 Bronze bucket (e.g., `raw-bucket-ccc-iot-2026`).


3. Click **Save**.

### Step 3: Increase Execution Timeout

Because this function will be processing large batches of SQS messages, it needs more than the default 3 seconds to run.

1. Go to the **Configuration** tab.
2. Select **General configuration** from the left-hand menu.
3. Click **Edit**.
4. Change the **Timeout** to **30 sec**.
5. Click **Save**.

### Step 4: Verify IAM Permissions (`LabRole`)

Your function needs the power to read from SQS and write to S3 (`s3:PutObject`).

1. Go to **Configuration > Permissions**.
2. Ensure the **Execution Role** is set to **`LabRole`**. If it isn't, click **Edit** and switch it.

### Step 5: Add the SQS Trigger & Batching

You need to tell the SQS queue to wake this function up whenever new IoT data arrives.

1. Go to your **Lambda function overview** at the top of the page.
2. Click **+ Add trigger**.
3. Select **SQS** from the dropdown menu.
4. Select your **SQS Queue** (e.g., `sqs-ccc-iot-2026`).
5. **Batch size:** Increase this to **100** or **500**. This forces a single Lambda instance to process a large chunk of messages at once, rather than spinning up a new instance for every single ESP32 ping. Also increase the **Batch window** to at least **1** second.
6. **Maximum Concurrency:** Set this to **2**. This throttles the trigger, preventing SQS from aggressively scaling up Lambda instances if a massive burst of IoT data arrives.
7. Click **Add**.

### Step 6: Set Reserved Concurrency (Lab Limit Protection)

To ensure your architecture stays safely under the strict AWS Academy / Lab limits (often capped at 10 concurrent instances total), you need to set a hard limit on this specific function.

1. Go to the **Configuration** tab, then select **Concurrency** on the left menu.
2. Click **Edit** under Reserved concurrency.
3. Set the **Reserved concurrency** to **3**.
4. Click **Save**. *(By capping this function at 3, you ensure it leaves plenty of room in your AWS account for your Data Processing and Data Querying Lambdas to run without crashing).*
