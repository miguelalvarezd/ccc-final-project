# Lambda Configuration Details

This is the most complex Lambda in the project. It talks to Athena, Secrets Manager, and Amazon Nova (via Bedrock), so it needs a bit more setup than the other two. Follow each section carefully.

**A. Lambda Layer (pydantic-ai)**

This function imports `pydantic_ai`, which is not included in the default Lambda runtime. You need to package it as a Lambda Layer.

1. On your local machine (or in CloudShell), run:
   ```bash
   mkdir -p python
   pip install "pydantic-ai-slim[bedrock]==1.58.0" \
    --target python/ \
    --platform manylinux_2_28_x86_64 \
    --python-version 3.13 \
    --implementation cp \
    --only-binary=:all: \
    --ignore-requires-python
   zip -r pydantic_ai_layer.zip python
   ```
2. In the **Lambda Console**, click **Layers** in the left menu -> **Create layer**.
3. **Name:** `pydantic-ai-layer`.
4. Upload the `pydantic_ai_layer.zip` file.
5. **Compatible runtimes:** Select **Python 3.14** (or whichever runtime your function uses).
6. Click **Create**.
7. Go back to your **lookup Lambda function**, scroll down to **Layers**, click **Add a layer**.
8. Choose **Custom layers**, select `pydantic-ai-layer`, and click **Add**.

**B. Secrets Manager (LLM API Key)**

The function reads an API key from AWS Secrets Manager to authenticate with Amazon Nova via the Pydantic AI gateway.

1. Navigate to the **Secrets Manager Console** -> **Store a new secret**.
2. **Secret type:** Other type of secret.
3. **Key/value pair:** Add a single row:
   * **Key:** `api_key` (or any key name — the code reads the first value).
   * **Value:** Your Pydantic AI Gateway API key.
4. Click **Next**.
5. **Secret name:** `LLM_API` (must match the code exactly).
6. Leave the rest as default and click **Store**.

**C. IAM Permissions (`LabRole`)**

Just like the other functions, go to **Configuration > Permissions**, click **Edit** on the Execution Role, and switch it to **`LabRole`**. This gives your function the permissions it needs:
* `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults` (query the Gold data).
* `s3:GetObject`, `s3:PutObject` on the Athena results bucket.
* `secretsmanager:GetSecretValue` (fetch the LLM API key).
* `bedrock:InvokeModel` (call Amazon Nova).

**D. VPC Configuration**

This Lambda must be attached to your VPC so it can securely reach AWS services through the endpoints you created in Phase 1.

1. Go to your Lambda function -> **Configuration** -> **VPC**.
2. Click **Edit**.
3. **VPC:** Select `parking-iot-vpc`.
4. **Subnets:** Select `parking-iot-private-subnet-1` and `parking-iot-private-subnet-2`.
5. **Security groups:** Select the default security group (or one that allows outbound HTTPS on port 443).
6. Click **Save**.

**E. Timeout**

Because this function calls Athena (polling for results) and the LLM (twice in RAG mode), it takes much longer than the default 3 seconds.

1. Go to **Configuration** -> **General configuration** -> **Edit**.
2. Change the **Timeout** to **`1 min 0 sec`**.
3. Optionally increase **Memory** to **256 MB** or **512 MB** for faster cold starts.
4. Click **Save**.

**F. The API Gateway Trigger**

This function is invoked by API Gateway, not by S3 or SQS. The trigger is created automatically when you set up the API Gateway integration in Phase 5 of the main README. Just verify:

1. Go to your Lambda function overview.
2. Under **Triggers**, you should see `ParkingDataAPI` (API Gateway) listed.
3. If not, go back to **API Gateway Console** -> `ParkingDataAPI` -> `/traffic` GET method, and make sure the **Lambda function** field points to this function.

*Don't forget to click **Deploy API** in the API Gateway console every time you change the integration!*
