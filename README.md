# Deployment Guide

## Phase 1: The Foundation (VPC, IGW, NAT, & Endpoints)

*This phase uses the AWS visual wizard to automatically generate your secure network environment, public/private subnets, and all the necessary routing in a single click.*

**1. Launch the VPC Wizard**

* Navigate to the **VPC Console** and click the orange **Create VPC** button.
* Under "Resources to create", select the **VPC and more** option.

**2. Configure the Network Layout**

* **Name tag auto-generation:** Type `parking-ccc-iot-2026`. (AWS will automatically prefix all your subnets, route tables, and gateways with this name!).
* **IPv4 CIDR block:** `10.0.0.0/16` (Leave as default).
* **Number of Availability Zones (AZs):** Select **2**.
* **Number of public subnets:** Select **2**.
* **Number of private subnets:** Select **2**.

**3. Add the Gateways and Endpoints**

* **NAT gateways ($):** Select **Zonal** and **In 1 AZ**.
* *What this does automatically:* AWS will create the NAT Gateway, put it in your public subnet, allocate an Elastic IP, and automatically configure your private route table to point to it so your Lambdas can reach the internet.


* **VPC endpoints:** Select **S3 Gateway**.
* *What this does automatically:* This creates a private tunnel straight to S3 and updates your route tables. Your Lambdas won't have to go over the public internet to drop files into your Bronze or Gold buckets, which makes it faster and more secure.


* **DNS options:** Ensure both **Enable DNS hostnames** and **Enable DNS resolution** are checked (they usually are by default).

**4. Create the Infrastructure**

* Look at the beautiful **Preview** diagram on the right side of the screen. You should see your VPC, the two subnets, the route tables, the IGW, and the NAT Gateway all neatly connected.
* Click **Create VPC** at the bottom right.
* *Note: It will take about 2 to 3 minutes to provision the NAT Gateway. Just grab a sip of water and wait for all the green checkmarks to appear!*

---

When you attach your Lambdas to this VPC later, you will just select the `parking-ccc-iot-2026-vpc` and the `parking-ccc-iot-2026-subnet-private1` and `parking-ccc-iot-2026-subnet-private2`, and everything will work perfectly out of the box.

---

**5. Create Security Groups (The Virtual Firewalls)**
*Navigate to the **VPC Console**, look at the left-hand menu under the "Security" section, and click on **Security Groups**.*

**A. Create the "All Outbound" Security Group**
*(This is for your Data Querying Lambda, which needs to reach out to the public internet to communicate with the LLM API).*

* Click the orange **Create security group** button.
* **Security group name:** `lambda-internet-sg`
* **Description:** `Allows Lambdas to reach the internet via NAT Gateway`
* **VPC:** Ensure you select your new `parking-ccc-iot-2026-vpc`.
* **Inbound rules:** Leave this completely empty. (Lambdas don't need inbound rules to receive traffic from API Gateway or S3 triggers).
* **Outbound rules:** AWS adds a default rule here that says **Type:** `All traffic`, **Destination:** `0.0.0.0/0`. Leave this exactly as it is! This allows the Lambda to send requests out to the web.
* Click **Create security group**.

**B. Create the "S3-Only" Security Group**
*(This is for your Data Ingestion and Processing Lambdas, which strictly move data between SQS and S3 buckets and should never talk to the public internet).*

* Click **Create security group** again.
* **Security group name:** `lambda-s3-only-sg`
* **Description:** `Restricts Lambda outbound traffic strictly to Amazon S3`
* **VPC:** Select your `parking-ccc-iot-2026-vpc`.
* **Inbound rules:** Leave empty.
* **Outbound rules:** 
    1. First, **Delete** the default `All traffic` -> `0.0.0.0/0` rule. (We are locking this down!).
    2. Click **Add rule**.
    3. **Type:** Select `HTTPS` (Port 443).
    4. **Destination:** Click the search box and select **Prefix lists**. Find the option that looks like `pl-xxxxxxx (com.amazonaws.us-east-1.s3)`.
* *Why this works:* This AWS Managed Prefix List automatically contains all the secure IP addresses for S3 in your region. Your Lambda can now talk to your Bronze and Gold buckets, but if a hacker ever compromised it, they couldn't exfiltrate data to the public internet!
* Click **Create security group**.

---

## Phase 2: The Data Lake Storage (S3)

*This phase creates the buckets that will hold your raw telemetry, processed data, and Athena logs.*

**1. Create the S3 Buckets**

* Navigate to the **S3 Console** -> **Create bucket**. You need to create three buckets with globally unique names. Based on your code, create exactly these:
* `raw-bucket-ccc-iot-2026` (The Bronze Bucket)
* `gold-bucket-ccc-iot-2026` (The Gold Bucket)
* `temporal-athena-ccc-iot-2026` (The Athena Results Bucket)

* *Note: Leave all buckets with "Block all public access" turned ON. Security first!*

**2. Configure the Athena Results Folder**

* Open `temporal-athena-ccc-iot-2026`, click **Create folder**, and name it `athena-results`.

---

## Phase 3: The Decoupling Buffer (SQS)

*This queue acts as a shock absorber. If 500 cars enter the parking lot at once, IoT Core dumps the messages here so your database doesn't crash.*

**1. Create the Queue**

* Navigate to the **SQS Console** -> **Create queue**.
* **Type:** Standard.
* **Name:** `sqs-ccc-iot-2026`.
* **Visibility timeout:** 2 minutes. 
* Leave the rest as default and click **Create queue**.

**2. Get the ARN**

* Once created, copy the **ARN** (Amazon Resource Name) from the queue details. You will need this for the IoT Rule.

---

## Phase 4: Edge Ingestion (AWS IoT Core)

*This phase registers your Raspberry Pi and tells AWS what to do when a message arrives.*

**1. Register the Device (Thing)**

* Navigate to **IoT Core Console** -> **Manage** -> **All devices** -> **Things** -> **Create things**.
* Choose **Create single thing** -> Name it `RaspberryPi_ZoneA`.
* Auto-generate a new certificate. Download the **Device Certificate**, **Public Key**, **Private Key**, and the **Amazon Root CA 1**. *(Save these safely! They go on the Raspberry Pi).*

**2. Create and Attach the Policy**

* Navigate to **Security** -> **Policies** -> **Create policy**.
* **Name:** `ParkingIoTPolicy`.
* **Action:** `iot:*` (For a lab, this is fine. For production, restrict to `iot:Connect` and `iot:Publish`).
* **Resource:** `*`
* **Effect:** Allow.
* Go back to your Certificates, select the one you generated, click **Actions** -> **Attach policy**, and select `ParkingIoTPolicy`.

**3. Create the IoT Rule (The Router)**

* Navigate to **Message Routing** -> **Rules** -> **Create rule**.
* **Name:** `RouteParkingDataToSQS`.
* **SQL Statement:** `SELECT * FROM 'parking/zoneA/spots'` (This assumes your Pi publishes to this MQTT topic).
* **Rule Actions:** * Select **Amazon SQS queue**.
* Choose your `iot-telemetry-queue`.
* **IAM Role:** Create a new role (e.g., `IoTSQSAccessRole`) to give IoT Core permission to write to SQS.

---

## Phase 5: The Frontend Door (API Gateway)

*This phase creates the HTTP endpoint that your React/HTML frontend will call to ask the LLM questions or get diagram data.*

**1. Create the API**

* Navigate to **API Gateway Console** -> **Create API**.
* Choose **REST API** (Not Private) -> **Build**.
* **API name:** `ParkingDataAPI`.
* **Endpoint Type:** Regional.

**2. Create the Resource and Method**

* Select the `/` root, click **Create resource**.
* **Resource Name:** `traffic` (This creates the `/traffic` path).
* Enable **CORS**.
* Select `/traffic`, click **Create method**.
* **Method type:** `GET`.
* **Integration type:** Lambda function.
* **Lambda proxy integration:** Toggle this **ON** (Crucial! This allows the query strings like `?mode=llm` to pass through).
* **Lambda function:** Select your Data Querying Lambda.

**3. Enable CORS (Cross-Origin Resource Sharing)**

* Select the `/traffic` resource, click **Enable CORS**.
* Leave the defaults (Allow GET, OPTIONS) and click **Save**. (This ensures your browser doesn't block the API call when you build your frontend).

**4. Deploy the API**

* Click **Deploy API**.
* **Stage:** New stage.
* **Stage name:** `prod`.
* Click **Deploy**.
* **Copy the Invoke URL!** It will look something like `https://abcdef123.execute-api.us-east-1.amazonaws.com/prod`.

---

## Phase 6: Lambda and Glue Configuration

Last, configure the Lambda functions, Glue Crawler, and Athena following the steps in the corresponding folders.

## You are officially fully deployed.

With this document, you can trace a data point's entire lifecycle:

1. The Pi detects a car and uses its certificates to publish to **IoT Core**.
2. The **IoT Rule** catches it and pushes it to **SQS**.
3. *[Your Ingestion Lambda]* reads SQS and drops it into the **Bronze S3 Bucket**.
4. *[Your Processing Lambda]* gets triggered by the Bronze S3 Bucket, cleans it, calculates availability, and saves it to the **Gold S3 Bucket**.
5. The **API Gateway** receives a user's web request, triggers the *[Data Querying Lambda]* (safely inside the **VPC**), which queries Athena (Gold Bucket) and Amazon Nova to return the answer!
