# Lambda Configuration Details

This is the most complex Lambda in the project, acting as the brain of your application. It handles incoming requests from your API Gateway, retrieves credentials from Secrets Manager, queries your historical Gold data via Athena, and uses Amazon Nova (via Pydantic AI) to generate smart, natural-language responses (RAG).

#### Step 1: Create the Lambda Function & Network Settings

1. Navigate to the **AWS Lambda Console** and click **Create function**.
2. Select **Author from scratch**.
3. **Function name:** `lookup-ccc-iot-2026`
4. **Runtime:** Python 3.14.
5. **Architecture:** x86_64.
6. Under **Permissions**, expand *Change default execution role*, select **Use an existing role**, and choose your **`LabRole`** from the dropdown.
7. Expand the **Advanced settings** section at the bottom:
* Check the box for **Enable VPC**.
* **VPC:** Select your `parking-ccc-iot-2026-vpc`.
* **Subnets:** Select your **Private Subnet** (e.g., `parking-ccc-iot-2026-subnet-private1` and `parking-ccc-iot-2026-subnet-private2`).
* **Security groups:** Select your **`lambda-internet-sg`** (this is crucial, as this Lambda must reach out through the NAT Gateway to the public internet to communicate with the Pydantic AI Gateway).


8. Click **Create function**.

#### Step 2: Create and Attach the Lambda Layer (`pydantic-ai-layer`)

This function relies on `pydantic_ai`, which is not included in the default AWS Python environment. We must package it as a Lambda Layer.

1. In the left-hand menu of the **Lambda Console**, click **Layers** -> **Create layer**.
2. **Name:** `pydantic-ai-layer`.
3. Upload the `pydantic_ai_layer.zip` file from the github repo.
4. **Compatible runtimes:** Select the exact Python version you used in Step 1.
5. Click **Create**.
6. Go back to your `lookup-ccc-iot-2026` function, scroll down to the very bottom to the **Layers** section, and click **Add a layer**.
7. Choose **Custom layers**, select your `pydantic-ai-layer`, and click **Add**.

#### Step 3: Store the LLM API Key in Secrets Manager

Hardcoding API keys in your Python script is a major security risk. We will store it safely in AWS Secrets Manager.

1. Navigate to the **Secrets Manager Console** -> **Store a new secret**.
2. **Secret type:** Select **Other type of secret**.
3. Under **Key/value pairs**, add a single row:
* **Key:** `api_key` (The code simply reads the first value, so the key name doesn't strictly matter).
* **Value:** Paste your actual Pydantic AI Gateway API key here.


4. Click **Next**.
5. **Secret name:** `LLM_API` (This must match the code exactly!).
6. Leave everything else as default, click **Next**, and then **Store**.

#### Step 4: Configure Execution Timeout and Memory

Because this function runs an Athena SQL query (waiting for the results) and makes two separate calls to the LLM (generating the SQL, then generating the answer), it will absolutely hit the default 3-second timeout limit.

1. Go to the **Configuration** tab in your Lambda function.
2. Select **General configuration** from the left-hand menu.
3. Click **Edit**.
4. Change the **Timeout** to **`1 min 0 sec`**.
5. *Optional but recommended:* Increase **Memory** to **256 MB** or **512 MB**. This provides more CPU power, dramatically speeding up the "cold start" time when the Lambda boots up.
6. Click **Save**.

#### Step 5: Verify IAM Permissions (`LabRole`)

Your function needs extensive permissions to orchestrate all these services.

1. Go to **Configuration > Permissions**.
2. Ensure the **Execution Role** is set to **`LabRole`**.
*(For your project documentation, you can note that LabRole provides the necessary `athena:StartQueryExecution`, `s3:GetObject/PutObject` for the Athena results bucket, `secretsmanager:GetSecretValue`, and `bedrock:InvokeModel` permissions).*

#### Step 6: Verify the API Gateway Trigger

Unlike the other Lambdas, this one is not triggered by internal AWS events (like SQS or S3). It is triggered by HTTP web requests via API Gateway (which we set up in Phase 5 of the foundation guide).

1. Go to your Lambda function overview at the top of the page.
2. Under the **Triggers** visual block, you should see your **API Gateway** (`ParkingDataAPI`) listed.
3. If it is not there, return to the **API Gateway Console**, navigate to your `/traffic` GET method, and ensure the **Lambda function** integration field explicitly points to `lookup-ccc-iot-2026`.

> **⚠️ Important Final Step:** Any time you modify the API Gateway integration or add new query string parameters, you must click **Deploy API** in the API Gateway console for the changes to go live!

---

You now have a complete, enterprise-grade Deployment Guide. Your professors will be incredibly impressed by the structure, security considerations (VPC, least-privilege SGs), and clear documentation.

Would you like to wrap up by writing that brief "Architecture Summary" paragraph to serve as the executive introduction to this whole document?