import os
from dotenv import load_dotenv
import openai

# Charger les variables d'environnement depuis le fichier .env (si présent)
load_dotenv()

# Configuration du modèle et du fournisseur
BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("GROQ_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Création du client compatible OpenAI / Groq / Ollama
kwargs = {}
if BASE_URL:
    kwargs["base_url"] = BASE_URL
if API_KEY:
    kwargs["api_key"] = API_KEY

client = openai.OpenAI(**kwargs)

def appeler_llm(prompt: str, *, model: str | None = None, temperature: float = 0.2, max_tokens: int = 500) -> str:
    """Appelle le modèle LLM d'OpenAI (v1) et renvoie la réponse textuelle.

    Parameters
    ----------
    prompt: str
        Le texte complet que l'on veut envoyer au LLM (rôle *user*).
    model: str | None, optional
        Le nom du modèle OpenAI à utiliser. Si None, utilise le modèle par défaut.
    temperature: float, default 0.2
        Niveau de créativité – 0 = déterministe, 1 = créatif.
    max_tokens: int, default 500
        Nombre maximal de tokens dans la réponse.

    Returns
    -------
    str
        Le contenu de la réponse du LLM, épuré des espaces superflus.
    """
    model_name = model or DEFAULT_MODEL
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # La réponse se trouve dans response.choices[0].message.content
        return response.choices[0].message.content.strip()
    except openai.APIError as e:
        # Gestion générique des erreurs de l'API OpenAI
        raise RuntimeError(f"Erreur API OpenAI : {e}")
    except Exception as e:
        # Capture tout autre problème (ex. problème réseau)
        raise RuntimeError(f"Erreur lors de l'appel à l'API OpenAI : {e}")

# Exemple d'utilisation directe (exécuté uniquement si le module est lancé en tant que script)
if __name__ == "__main__":
    test_prompt = "Génère une courte description en français d'une colonne nommée 'NB_LOGEMENTS' pour le projet BDDMAS."
    print("Prompt :", test_prompt)
    print("Réponse :")
    print(appeler_llm(test_prompt))
