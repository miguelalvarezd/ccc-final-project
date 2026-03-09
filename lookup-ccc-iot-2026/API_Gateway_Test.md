# Test Lookup Lambda in API

Depending on what URL you type, the lambda will handle deterministic lookup and natural language:

**1. To test the AI Assistant:**
`YOUR_API_URL/prod/traffic?mode=llm&prompt=Where%20can%20I%20park%20right%20now?`

**2. To fetch raw JSON for a frontend visual diagram:**
`YOUR_API_URL/prod/traffic?mode=filters&device_id=pi-zone-A&limit=10`