# Lambda Configuration Details

To make this function work perfectly in your AWS lab environment, you need to configure a few things:

**A. Environment Variables**

* **Key:** `GOLD_BUCKET_NAME`
* **Value:** The exact name of your S3 Gold bucket (e.g., `gold-bucket-ccc-iot-2026`).

**B. IAM Permissions (`LabRole`)**
Just like the last function, you need to go to **Configuration > Permissions**, click **Edit** on the Execution Role, and switch it to **`LabRole`**. This gives your function the power to both `s3:GetObject` (read from Bronze) and `s3:PutObject` (write to Gold).

**C. The S3 Trigger**
You need to tell the Bronze bucket to wake this function up!

1. Go to your **Lambda function overview**.
2. Click **+ Add trigger**.
3. Select **S3** from the dropdown menu.
4. Select your **Bronze Bucket**.
5. Event type should be **All object create events**.
6. Acknowledge the recursive invocation warning and click **Add**.

*Important Architecture Note:* Never set an S3 trigger to output to the *same* bucket it is reading from, or you will create an infinite loop that can drain your AWS credits in minutes. Always read from Bronze, write to Gold!