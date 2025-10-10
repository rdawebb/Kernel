"""Summariser module for generating email summaries."""

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

class EmailSummariser:
    """Class to summarise email content using LSA algorithm"""

    def __init__(self, language: str = "english", sentence_count: int = 3):
        self.language = language
        self.sentence_count = sentence_count
        self.summarizer = LsaSummarizer()
    
    def summarise(self, text: str) -> str:
        """Generate a summary of the provided text"""
        parser = PlaintextParser.from_string(text, Tokenizer(self.language))
        summary_sentences = self.summarizer(parser.document, self.sentence_count)
        summary = ' '.join(str(sentence) for sentence in summary_sentences)
        return summary if summary else "No summary available."