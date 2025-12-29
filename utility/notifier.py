
import os
from mailjet_rest import Client
import datetime

class Notifier:
    def __init__(self, api_key: str = None, api_secret: str = None):
        # Allow passing keys, or fall back to Env Vars
        self.api_key = api_key or os.environ.get("MAILJET_API_KEY")
        self.api_secret = api_secret or os.environ.get("MAILJET_API_SECRET")
        
        if self.api_key and self.api_secret:
            self.client = Client(auth=(self.api_key, self.api_secret), version='v3.1')
            self.enabled = True
        else:
            print("WARNING: Mailjet API Keys not found. Notifications disabled.")
            self.client = None
            self.enabled = False

    def send_decision(self, recipient_email: str, decisions: list[str]):
        """
        Send an email with the investment decisions.
        :param recipient_email: The email address to send to.
        :param decisions: A list of strings, each describing a decision (e.g. "Buy 100 GOOGL").
        """
        if not self.enabled:
            print(f"Skipping email to {recipient_email}: Mailjet not configured.")
            return

        if not decisions:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build HTML content
        html_content = f"<h3>Investment Decisions - {timestamp}</h3><ul>"
        for decision in decisions:
            html_content += f"<li>{decision}</li>"
        html_content += "</ul><p>Please review and execute manually if approved.</p>"

        data = {
          'Messages': [
            {
              'From': {
                'Email': "pilot@mailjet.com", # Default sender, ideally configured by user
                'Name': "Financial Simulator"
              },
              'To': [
                {
                  'Email': recipient_email,
                  'Name': "Investor"
                }
              ],
              'Subject': f"Investment Alert: {len(decisions)} Action(s) Required",
              'TextPart': f"Investment Decisions for {timestamp}:\n\n" + "\n".join(decisions),
              'HTMLPart': html_content,
              'CustomID': "FinancialSimDecision"
            }
          ]
        }
        
        try:
            result = self.client.send.create(data=data)
            if result.status_code == 200:
                print(f"Email sent successfully to {recipient_email}")
            else:
                print(f"Failed to send email: {result.status_code} - {result.json()}")
        except Exception as e:
            print(f"Error sending email: {e}")

if __name__ == "__main__":
    # Test
    # export MAILJET_API_KEY=...
    # export MAILJET_API_SECRET=...
    notifier = Notifier()
    if notifier.enabled:
        notifier.send_decision("test@example.com", ["Buy 100 AAPL at $150", "Sell 50 GOOGL at $2800"])
