import os
from dotenv import load_dotenv
import openai

# Charger les variables d'environnement depuis le fichier .env (si présent)
load_dotenv()

# Configuration du modèle et du fournisseur
BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("GROQ_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_client = None


def llm_disponible() -> bool:
    """Vrai si un fournisseur est configuré (clé API, ou URL locale type Ollama) et l'IA non désactivée."""
    if os.getenv("BDDMAS_LLM", "1").strip().casefold() in {"0", "non", "false", "off"}:
        return False
    return bool(API_KEY or BASE_URL)


def _obtenir_client() -> openai.OpenAI:
    """Client compatible OpenAI / Groq / Ollama, créé au premier appel (l'import ne plante pas sans clé)."""
    global _client
    if _client is None:
        # Plusieurs essais : le quota gratuit Groq (tokens par minute) renvoie vite une erreur 429,
        # le SDK attend alors le délai indiqué par le serveur avant de réessayer
        kwargs = {"timeout": 60, "max_retries": 3}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        # Ollama n'exige pas de clé, mais le SDK en veut une
        kwargs["api_key"] = API_KEY or "sans-cle"
        _client = openai.OpenAI(**kwargs)
    return _client


def appeler_llm(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 500,
    systeme: str | None = None,
    format_json: bool = False,
) -> str:
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
    systeme: str | None, optional
        Consignes envoyées avec le rôle *system*.
    format_json: bool, default False
        Demande une réponse JSON (ignoré si le fournisseur ne le gère pas).

    Returns
    -------
    str
        Le contenu de la réponse du LLM, épuré des espaces superflus.
    """
    model_name = model or DEFAULT_MODEL
    messages = [{"role": "user", "content": prompt}]
    if systeme:
        messages.insert(0, {"role": "system", "content": systeme})
    parametres = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        client = _obtenir_client()
        try:
            if format_json:
                response = client.chat.completions.create(**parametres, response_format={"type": "json_object"})
            else:
                response = client.chat.completions.create(**parametres)
        except openai.BadRequestError:
            if not format_json:
                raise
            # Fournisseur sans mode JSON : la consigne du prompt suffit
            response = client.chat.completions.create(**parametres)
        # La réponse se trouve dans response.choices[0].message.content
        return (response.choices[0].message.content or "").strip()
    except openai.APIError as e:
        # Gestion générique des erreurs de l'API OpenAI
        raise RuntimeError(f"Erreur API OpenAI : {e}")
    except Exception as e:
        # Capture tout autre problème (ex. problème réseau)
        raise RuntimeError(f"Erreur lors de l'appel à l'API OpenAI : {e}")

# Exemple d'utilisation directe (exécuté uniquement si le module est lancé en tant que script)
if __name__ == "__main__":
    test_prompt = "Génère une courte description en français d'une colonne nommée 'NB_LOGEMENTS' pour le projet BDDMAS."
    print("Prompt :", test_prompt)
    print("Réponse :")
    print(appeler_llm(test_prompt))
