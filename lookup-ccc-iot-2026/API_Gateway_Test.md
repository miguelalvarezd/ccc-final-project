### ⚠️ One Last Vital Check Before You Test!

Because this script now talks to Nova, waits for Athena, and then talks to Nova again, **it will take longer than 3 seconds to run**.

If you do not increase the Lambda timeout, AWS will kill the script at the 3-second mark, and API Gateway will return a generic error.

1. In the Lambda Console, go to the **Configuration** tab.
2. Click **General configuration** on the left menu.
3. Click **Edit**.
4. Change the **Timeout** from `0 min 3 sec` to **`1 min 0 sec`**.
5. Click **Save**.

### How to test your new Unified API

Now, depending on what URL you type, your Lambda will handle it perfectly:

**1. To test the AI Assistant (RAG):**
`YOUR_API_URL/prod/traffic?mode=llm&prompt=Where%20can%20I%20park%20right%20now?`

**2. To fetch raw JSON for a frontend visual diagram:**
`YOUR_API_URL/prod/traffic?mode=filters&device_id=pi-zone-A&limit=10`

*(Don't forget to **Deploy** the new code in the Lambda console, and ensure your timeout is set to 1 minute!)* Would you like me to write a quick HTML page that you can run on your computer to test both of these endpoints with real buttons?