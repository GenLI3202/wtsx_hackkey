import unittest
from agent.client import WatsonXAgent

class TestWatsonXAgent(unittest.TestCase):
    def setUp(self):
        self.agent = WatsonXAgent()

    def test_chat(self):
        response = self.agent.chat("Hello")
        self.assertTrue(isinstance(response, str))

if __name__ == '__main__':
    unittest.main()
