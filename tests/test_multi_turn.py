import requests


API_URL = "http://localhost:8080/chat"


def send_message(message, session_id=None):
    payload = {"message": message, "debug": True}
    if session_id:
        payload["session_id"] = session_id
    response = requests.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def print_result(turn, message, result):
    print(f"Turn {turn}")
    print(f"User: {message}")
    print(f"Commentary: {result['commentary']}")
    if result.get("table"):
        print(f"Rows: {len(result['table'])}")
        for row in result["table"][:3]:
            print(row)
    if result.get("debug"):
        print(result["debug"].get("plan"))


def main():
    print("Multi-turn conversation test")
    session_id = None
    messages = [
        "Show the 5 stocks with the highest traded value",
        "Show Tencent's price trend from 2025-01-01 to 2025-01-31",
        "Did Tencent look unusually active today?",
    ]
    for index, message in enumerate(messages, start=1):
        try:
            result = send_message(message, session_id)
            session_id = result.get("session_id")
            print_result(index, message, result)
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API service. Start the backend first.")
            break
        except requests.exceptions.RequestException as exc:
            print(f"Turn {index} failed: {exc}")
            break
    print("Test complete")


if __name__ == "__main__":
    main()
