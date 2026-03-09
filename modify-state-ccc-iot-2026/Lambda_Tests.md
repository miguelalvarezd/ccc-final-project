# Modify State Lambda Test

There are two alternatives to testing the `modify-state-ccc-iot-2026` lambda: through lambda test, or through the API.

## Lambda Test

Create two tests, one to test introducing an available spot, and another for a booked spot. The files for the tests are included in `modify-state-ccc-iot-2026/TestAvailable.json` and `modify-state-ccc-iot-2026/TestBooked.json`.

## API Test

You can also test the lambda through the API:

```bash
curl -X POST https://pmv073dn7k.execute-api.eu-west-1.amazonaws.com/prod/traffic/state \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_id": "spot-02",
    "state": "BOOKED",
    "license_plate": "7110JFR",
    "booked_until": "2026-03-01T10:00:00Z"
  }'
```