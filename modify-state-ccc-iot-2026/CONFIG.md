# Lambda Configuration Details

This lambda is responsible for updating the current state of each parking spot (*AVAILABLE*, *BOOKED*, *MAINTENANCE*) in the DynamoDB.

## Step 1: Create the Lambda Function & Network Settings

1. Navigate to the **AWS Lambda Console** and click **Create function**.
2. Select **Author from scratch**.
3. **Function name:** `modify-state-ccc-iot-2026`
4. **Runtime:** Python 3.14.
5. **Architecture:** x86_64.
6. Under **Permissions**, expand *Change default execution role*, select **Use an existing role**, and choose your **`LabRole`** from the dropdown.
7. Expand the **Advanced settings** section at the bottom:
    * Check the box for **Enable VPC**.
    * **VPC:** Select your `parking-ccc-iot-2026-vpc`.
    * **Subnets:** Select your **Private Subnet** (e.g., `parking-ccc-iot-2026-subnet-private1` and `parking-ccc-iot-2026-subnet-private2`).
    * **Security groups:** Select your **`lambda-internet-sg`** (this is crucial, as this Lambda must reach out through the NAT Gateway to the public internet to communicate with the Pydantic AI Gateway) and **`lambda-dynamobd-only-sg`** (so that it can access DynamoDB. Note that the first SG already allows it, but it's good to have granularity).
8. Click **Create function**.

## Step 2: Configure Execution Timeout and Memory

This function only has to access DynamoDB.

1. Go to the **Configuration** tab in your Lambda function.
2. Select **General configuration** from the left-hand menu.
3. Click **Edit**.
4. Change the **Timeout** to **`0 min 10 sec`**.
5. Click **Save**.

## Step 3: Configure Concurrency

We are limiting this lambda function to a maximum of 1 concurrent executions. This way, we will have, at most, 9 concurrent lambdas (3 for ingestion and processing each, 2 for lookup, 1 for modifying the state).

1. Go to the **Configuration** tab, then select **Concurrency** on the left menu.
2. Click **Edit** under Reserved concurrency.
3. Set the **Reserved concurrency** to **1**.
4. Click **Save**.

## Step 4: Verify IAM Permissions (`LabRole`)

Your function needs extensive permissions to orchestrate all these services.

1. Go to **Configuration > Permissions**.
2. Ensure the **Execution Role** is set to **`LabRole`**.

## Step 5: Verify the API Gateway Trigger

Unlike the other Lambdas, this one is not triggered by internal AWS events (like SQS or S3). It is triggered by HTTP web requests via API Gateway (which we set up in Phase 5 of the foundation guide).

1. Go to your Lambda function overview at the top of the page.
2. Under the **Triggers** visual block, you should see your **API Gateway** (`ParkingDataAPI`) listed.
3. If it is not there, return to the **API Gateway Console**, navigate to your `/traffic/state` POST method, and ensure the **Lambda function** integration field explicitly points to `modify-state-ccc-iot-2026`.

> **⚠️ Important Final Step:** Any time you modify the API Gateway integration or add new query string parameters, you must click **Deploy API** in the API Gateway console for the changes to go live!