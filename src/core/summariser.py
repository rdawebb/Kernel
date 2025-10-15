"""Summariser module for generating email summaries."""

import subprocess
import sys
from utils import logger
from utils.config import load_config

config = load_config()
logger = logger.get_logger()

class EmailSummariser:
    """Class to summarise email content using LSA algorithm"""

    installed_models = {"sumy": False, 
                        "minibart": False, 
                        "t5": False,
                        "bart": False, 
                        "openai": False, 
                        "cohere": False,
                        "ollama": False
                        }

    def __init__(self):
        self.reload_config()

    def reload_config(self):
        cfg = load_config()
        self.language = cfg.get("language", "english")
        self.sentence_count = cfg.get("sentence_count", 3)
        self.summarizer = cfg.get("default_summariser", "sumy")

    @staticmethod
    def install(package):
        """Install a package using pip"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except Exception as e:
            logger.error(f"Error installing {package}: {e}")

    @staticmethod
    def uninstall(package):
        """Uninstall a package using pip"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package])
        except Exception as e:
            logger.error(f"Error uninstalling {package}: {e}")

    def choose_model(self, choice: int):
        """Choose the summarization model to use"""
        model_map = {
            1: "sumy",
            2: "minibart",
            3: "t5",
            4: "bart",
            5: "openai",
            6: "cohere",
            7: "ollama"
        }
        selected_model = model_map.get(choice)
        
        if not selected_model:
            logger.error("Invalid model choice.")
            return
        
        if selected_model == self.summarizer:
            logger.info(f"Model {selected_model} is already selected.")
            return
            
        self.summarizer = selected_model
        config["default_summariser"] = selected_model
        
        if not self.installed_models[selected_model]:
            logger.info(f"Installing model: {selected_model}...")
            self.install(selected_model)
            self.installed_models[selected_model] = True

        self.delete_unused_models(selected_model)
        logger.info(f"Selected summarization model: {selected_model}")

    def delete_unused_models(self, selected_model: str):
        """Uninstall unused models to save space"""
        for model in self.installed_models:
            if model != selected_model and self.installed_models[model]:
                self.uninstall(model)
                self.installed_models[model] = False

    def summarise_with_sumy(self, email: str) -> str:
        """Generate a summary of the provided email text using the Sumy library"""
        try:
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.lsa import LsaSummarizer
        except ImportError:
            logger.error("Sumy library is not installed. Please install it to use LSA summarization.")
            return "No summary available."

        try:
            parser = PlaintextParser.from_string(email, Tokenizer(self.language))
            summariser = LsaSummarizer()
            summary = summariser(parser.document, self.sentence_count)
            summary_text = ' '.join(str(sentence) for sentence in summary)
            return summary_text if summary_text else "No summary available."
        except Exception as e:
            logger.error(f"Error during Sumy summarization: {e}")
            return "No summary available."

    def summarise_with_minibart(self, email: str) -> str:
        """Generate a summary of the provided email text using the MiniBart model"""
        try:
            from transformers import pipeline
        except ImportError:
            logger.error("Transformers library is not installed. Please install it to use MiniBart summarization.")
            return "No summary available."
        
        try:
            summarizer = pipeline("summarization", model=config.get("minibart_model", "facebook/bart-mini"))
            summary_list = summarizer(email, max_length=130, min_length=30, do_sample=False)
            summary = summary_list[0]['summary_text']
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during MiniBart summarization: {e}")
            return "No summary available."

    def summarise_with_t5(self, email: str) -> str:
        """Generate a summary of the provided email text using the T5 model"""
        try:
            from transformers import pipeline
        except ImportError:
            logger.error("Transformers library is not installed. Please install it to use T5 summarization.")
            return "No summary available."

        try:
            summarizer = pipeline("summarization", model="t5-base")
            summary_list = summarizer(email, max_length=130, min_length=30, do_sample=False)
            summary = summary_list[0]['summary_text']
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during T5 summarization: {e}")
            return "No summary available."

    def summarise_with_bart(self, email: str) -> str:
        """Generate a summary of the provided email text using the BART model"""
        try:
            from transformers import pipeline
        except ImportError:
            logger.error("Transformers library is not installed. Please install it to use BART summarization.")
            return "No summary available."

        try:
            summarizer = pipeline("summarization", model=config.get("bart_model", "facebook/bart-large-cnn"))
            summary_list = summarizer(email, max_length=130, min_length=30, do_sample=False)
            summary = summary_list[0]['summary_text']
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during BART summarization: {e}")
            return "No summary available."

    def summarise_with_openai(self, email: str) -> str:
        """Generate a summary of the provided email text using OpenAI's GPT-4 model"""
        try:
            import openai
        except ImportError:
            logger.error("OpenAI library is not installed. Please install it to use OpenAI summarization.")
            return "No summary available."

        try:
            openai.api_key = config.get("openai_api_key")
            response = openai.ChatCompletion.create(
                model=config.get("openai_model", "gpt-4"),
                messages=[
                    {"role": "user", "content": f"Summarize the following text:\n\n{email}\n\nSummary:"}
                ]
            )
            summary = response.choices[0].message.content.strip()
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during OpenAI summarization: {e}")
            return "No summary available."
        
    def summarise_with_cohere(self, text: str) -> str:
        """Generate a summary using Cohere's Command R model"""
        try:
            import cohere
        except ImportError:
            logger.error("Cohere library is not installed. Please install it to use Cohere summarization.")
            return "No summary available."

        try:
            co = cohere.Client(config.get("cohere_api_key"))
            response = co.summarize(
                text=text,
                length='medium',
                format='paragraph',
                model=config.get("cohere_model", "command-r"),
                additional_command='',
                temperature=0.3,
                k=0,
                p=0.75,
                repetition_penalty=1.2,
                stop_sequences=[],
                return_likelihoods='NONE'
            )
            summary = response.summary
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during Cohere summarization: {e}")
            return "No summary available."
        
    def summarise_with_ollama(self, text: str) -> str:
        """Generate a summary using Ollama's model"""
        try:
            import ollama
        except ImportError:
            logger.error("Ollama library is not installed. Please install it to use Ollama summarization.")
            return "No summary available."

        try:
            client = ollama.Ollama()
            response = client.chat(
                model=config.get("ollama_model", "llama2"),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes emails."},
                    {"role": "user", "content": f"Summarize the following text:\n\n{text}"}
                ]
            )
            summary = response['choices'][0]['message']['content'].strip()
            return summary if summary else "No summary available."
        except Exception as e:
            logger.error(f"Error during Ollama summarization: {e}")
            return "No summary available."

    def main(self, text: str) -> str:
        """Main method to generate summary using the selected model"""
        if self.summarizer:
            return self.summarizer(text)
        else:
            logger.warning("No summarization model selected.")
            return "No summary available."