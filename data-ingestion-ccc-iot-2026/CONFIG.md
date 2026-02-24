# Lambda Configuration Details

To make this function work perfectly in your AWS lab environment, you need to configure a few things:

**A. Environment Variables**

* **Key:** `BRONZE_BUCKET_NAME`
* **Value:** The exact name of your S3 Gold bucket (e.g., `raw-bucket-ccc-iot-2026`).

**B. IAM Permissions (`LabRole`)**
You need to go to **Configuration > Permissions**, click **Edit** on the Execution Role, and switch it to **`LabRole`**. This gives your function the power to `s3:PutObject` (write to Bronze).

**C. The SQS Trigger**
You need to tell the Bronze bucket to wake this function up!

1. Go to your **Lambda function overview**.
2. Click **+ Add trigger**.
3. Select **SQS** from the dropdown menu.
4. Select your **SQS Queue**.
