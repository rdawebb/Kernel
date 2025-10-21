"""Summariser module for generating email summaries."""

from src.utils import log_manager
from src.utils.config import load_config
from src.utils.model_manager import ModelManager

log_manager = log_manager.get_logger()


class EmailSummariser:
    """Class to summarise email content using various models"""

    def __init__(self):
        self.model_manager = ModelManager()
        self.config = load_config()
        self.reload_config()

    def reload_config(self):
        """Reload configuration settings"""
        self.config = load_config()
        self.language = self.config.get("language", "english")
        self.sentence_count = self.config.get("sentence_count", 3)
        self.model_manager.reload_config()

    def _safe_import(self, library_name, import_path, error_message):
        """Safely import a library and handle ImportError."""
        try:
            parts = import_path.split()
            if parts[0] == 'from':
                # Handle "from x import y" style
                module_name = parts[1]
                import_name = parts[3]
                module = __import__(module_name, fromlist=[import_name])
                return getattr(module, import_name), True
            else:
                # Handle simple "import x" style
                module = __import__(import_path)
                return module, True
        except ImportError:
            log_manager.error(error_message)
            return None, False

    def _execute_safely(self, func, error_prefix):
        """Execute a function safely with error handling."""
        try:
            return func()
        except Exception as e:
            log_manager.error(f"Error during {error_prefix}: {e}")
            return None

    def _format_summary(self, summary):
        """Return summary text or fallback message if empty."""
        return summary if summary else "No summary available."

    def _summarise_with_library(self, text: str, library_name: str, import_statement: str, 
                               summarize_func, error_prefix: str) -> str:
        """Generic summarization with unified import and execution handling."""
        try:
            # Try to import the library
            __import__(import_statement.split()[1] if 'from' in import_statement else import_statement)
        except ImportError:
            log_manager.error(f"{library_name} library is not installed. Please install it to use {error_prefix} summarization.")
            return "No summary available."

        result = self._execute_safely(summarize_func, error_prefix)
        return result if result else "No summary available."

    def summarise_with_sumy(self, email: str) -> str:
        """Generate a summary of the provided email text using the Sumy library"""
        def summarize():
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.lsa import LsaSummarizer
            
            parser = PlaintextParser.from_string(email, Tokenizer(self.language))
            summariser = LsaSummarizer()
            summary = summariser(parser.document, self.sentence_count)
            summary_text = ' '.join(str(sentence) for sentence in summary)
            return self._format_summary(summary_text)

        return self._summarise_with_library(
            email,
            "Sumy",
            "from sumy.parsers.plaintext import PlaintextParser",
            summarize,
            "Sumy summarization"
        )

    def _summarise_with_transformer(self, email: str, model_name: str, config_key: str, 
                                   default_model: str, error_prefix: str) -> str:
        """Generic transformer-based summarization (MiniBart, T5, BART)."""
        def summarize():
            from transformers import pipeline
            
            model = self.config.get(config_key, default_model)
            summarizer = pipeline("summarization", model=model)
            summary_list = summarizer(email, max_length=130, min_length=30, do_sample=False)
            summary = summary_list[0]['summary_text']
            return self._format_summary(summary)

        return self._summarise_with_library(
            email,
            "Transformers",
            "from transformers import pipeline",
            summarize,
            error_prefix
        )

    def summarise_with_minibart(self, email: str) -> str:
        """Generate a summary using the MiniBart model"""
        return self._summarise_with_transformer(
            email, 
            "MiniBart", 
            "minibart_model", 
            "facebook/bart-mini",
            "MiniBart summarization"
        )

    def summarise_with_t5(self, email: str) -> str:
        """Generate a summary using the T5 model"""
        return self._summarise_with_transformer(
            email, 
            "T5", 
            "t5_model", 
            "t5-base",
            "T5 summarization"
        )

    def summarise_with_bart(self, email: str) -> str:
        """Generate a summary using the BART model"""
        return self._summarise_with_transformer(
            email, 
            "BART", 
            "bart_model", 
            "facebook/bart-large-cnn",
            "BART summarization"
        )

    def summarise_with_openai(self, email: str) -> str:
        """Generate a summary using OpenAI's GPT-4 model"""
        def summarize():
            import openai
            
            openai.api_key = self.config.get("openai_api_key")
            response = openai.ChatCompletion.create(
                model=self.config.get("openai_model", "gpt-4"),
                messages=[
                    {"role": "user", "content": f"Summarize the following text:\n\n{email}\n\nSummary:"}
                ]
            )
            summary = response.choices[0].message.content.strip()
            return self._format_summary(summary)

        return self._summarise_with_library(
            email,
            "OpenAI",
            "import openai",
            summarize,
            "OpenAI summarization"
        )
        
    def summarise_with_cohere(self, text: str) -> str:
        """Generate a summary using Cohere's Command R model"""
        def summarize():
            import cohere
            
            co = cohere.Client(self.config.get("cohere_api_key"))
            response = co.summarize(
                text=text,
                length='medium',
                format='paragraph',
                model=self.config.get("cohere_model", "command-r"),
                additional_command='',
                temperature=0.3,
                k=0,
                p=0.75,
                repetition_penalty=1.2,
                stop_sequences=[],
                return_likelihoods='NONE'
            )
            return self._format_summary(response.summary)

        return self._summarise_with_library(
            text,
            "Cohere",
            "import cohere",
            summarize,
            "Cohere summarization"
        )
        
    def summarise_with_ollama(self, text: str) -> str:
        """Generate a summary using Ollama's model"""
        def summarize():
            import ollama
            
            client = ollama.Ollama()
            response = client.chat(
                model=self.config.get("ollama_model", "llama2"),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes emails."},
                    {"role": "user", "content": f"Summarize the following text:\n\n{text}"}
                ]
            )
            summary = response['choices'][0]['message']['content'].strip()
            return self._format_summary(summary)

        return self._summarise_with_library(
            text,
            "Ollama",
            "import ollama",
            summarize,
            "Ollama summarization"
        )

    def main(self, text: str) -> str:
        """Main method to generate summary using the selected model"""
        current_model = self.model_manager.get_current_model()
        
        if not current_model:
            log_manager.warning("No summarization model selected.")
            return "No summary available."
        
        # Map model names to their corresponding methods
        model_methods = {
            "sumy": self.summarise_with_sumy,
            "minibart": self.summarise_with_minibart,
            "t5": self.summarise_with_t5,
            "bart": self.summarise_with_bart,
            "openai": self.summarise_with_openai,
            "cohere": self.summarise_with_cohere,
            "ollama": self.summarise_with_ollama
        }
        
        method = model_methods.get(current_model)
        if method:
            return method(text)
        else:
            log_manager.error(f"Unknown model: {current_model}")
            return "No summary available."