from typing import Dict, List, Union, Any, Callable
from core.data_classes import RetrieverOutput, Document

# TODO: delete component here
from core.component import Component

# TODO: import all other  functions into this single file to be exposed to users


def compose_model_kwargs(default_model_kwargs: Dict, model_kwargs: Dict) -> Dict:
    r"""
    The model configuration exclude the input itself.
    Combine the default model, model_kwargs with the passed model_kwargs.
    Example:
    model_kwargs = {"temperature": 0.5, "model": "gpt-3.5-turbo"}
    self.model_kwargs = {"model": "gpt-3.5"}
    combine_kwargs(model_kwargs) => {"temperature": 0.5, "model": "gpt-3.5-turbo"}

    """
    pass_model_kwargs = default_model_kwargs.copy()

    if model_kwargs:
        pass_model_kwargs.update(model_kwargs)
    return pass_model_kwargs


def retriever_output_to_context_str(
    retriever_output: Union[RetrieverOutput, List[RetrieverOutput]],
    deduplicate: bool = False,
) -> str:
    r"""The retrieved documents from one or mulitple queries.
    Deduplicate is especially helpful when you used query expansion.
    """
    """
    How to combine your retrieved chunks into the context is highly dependent on your use case.
    If you used query expansion, you might want to deduplicate the chunks.
    """
    chunks_to_use: List[Document] = []
    context_str = ""
    sep = " "
    if isinstance(retriever_output, RetrieverOutput):
        chunks_to_use = retriever_output.documents
    else:
        for output in retriever_output:
            chunks_to_use.extend(output.documents)
    if deduplicate:
        unique_chunks_ids = set([chunk.id for chunk in chunks_to_use])
        # id and if it is used, it will be True
        used_chunk_in_context_str: Dict[Any, bool] = {
            id: False for id in unique_chunks_ids
        }
        for chunk in chunks_to_use:
            if not used_chunk_in_context_str[chunk.id]:
                context_str += sep + chunk.text
                used_chunk_in_context_str[chunk.id] = True
    else:
        context_str = sep.join([chunk.text for chunk in chunks_to_use])
    return context_str


import hashlib
import json


def generate_component_key(component: Component) -> str:
    """
    Generates a unique key for a Component instance based on its type,
    version, configuration, and nested components.
    """
    # Start with the basic information: class name and version
    key_parts = {
        "class_name": component._get_name(),
        "version": getattr(component, "_version", 0),
    }

    # If the component stores configuration directly, serialize this configuration
    if hasattr(component, "get_config"):
        config = (
            component.get_config()
        )  # Ensure this method returns a serializable dictionary
        key_parts["config"] = json.dumps(config, sort_keys=True)

    # If the component contains other components, include their keys
    if hasattr(component, "_components") and component._components:
        nested_keys = {}
        for name, subcomponent in component._components.items():
            if subcomponent:
                nested_keys[name] = generate_component_key(subcomponent)
        key_parts["nested"] = nested_keys

    # Serialize key_parts to a string and hash it
    key_str = json.dumps(key_parts, sort_keys=True)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def generate_readable_key_for_function(fn: Callable) -> str:

    module_name = fn.__module__
    function_name = fn.__name__
    return f"{module_name}.{function_name}"


"""
All of these algorithms have been taken from the paper:
Trotmam et al, Improvements to BM25 and Language Models Examined

Here we implement all the BM25 variations mentioned. 
"""


# https://en.wikipedia.org/wiki/Okapi_BM25
# word can be a token or a real word
# Trotmam et al, Improvements to BM25 and Language Models Examined
"""
Retrieval is highly dependent on the database.

db-> transformer -> (index) should be a pair
LocalDocumentDB:  [Local Document RAG]
(1) algorithm, (2) index, build_index_from_documents (3) retrieve (top_k, query)

What algorithm will do for LocalDocumentDB:
(1) Build_index_from_documents (2) retrieval initialization (3) retrieve (top_k, query), potentially with score.

InMemoryRetriever: (Component)
(1) load_documents (2) build_index_from_documents (3) retrieve (top_k, query)

PostgresDB:
(1) sql_query for retrieval (2) pg_vector for retrieval (3) retrieve (top_k, query)

MemoryDB:
(1) chat_history (2) provide different retrieval methods, allow specify retrievel method at init.

Generator:
(1) prompt
(2) api_client (model)
(3) output_processors

Retriever
(1) 
"""

import re
from typing import Any, Dict, List
import json


def extract_json_str(text: str, add_missing_right_brace: bool = True) -> str:
    """
    Extract JSON string from text.
    NOTE: Only handles the first JSON object found in the text. And it expects at least one JSON object in the text.
    If right brace is not found, we add one to the end of the string.
    """
    # NOTE: this regex parsing is taken from langchain.output_parsers.pydantic
    text = text.strip().replace("{{", "{").replace("}}", "}")
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in the text: {text}")

    # Attempt to find the matching closing brace
    brace_count = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1

        if brace_count == 0:
            end = i
            break

    if end == -1 and add_missing_right_brace:
        # If no closing brace is found, but we are allowed to add one
        text += "}"
        end = len(text) - 1
    elif end == -1:
        raise ValueError(
            "Incomplete JSON object found and add_missing_right_brace is False."
        )

    return text[start : end + 1]


def extract_list_str(text: str, add_missing_right_bracket: bool = True) -> str:
    """
    Extract the first complete list string from the provided text. If the list string is incomplete
    (missing the closing bracket), an option allows adding a closing bracket at the end.

    Args:
        text (str): The text containing potential list data.
        add_missing_right_bracket (bool): Whether to add a closing bracket if it is missing.

    Returns:
        str: The extracted list string.

    Raises:
        ValueError: If no list is found or if the list extraction is incomplete
                    without the option to add a missing bracket.
    """
    text = text.strip()
    start = text.find("[")
    if start == -1:
        raise ValueError("No list found in the text.")

    # Attempt to find the matching closing bracket
    bracket_count = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "[":
            bracket_count += 1
        elif text[i] == "]":
            bracket_count -= 1

        if bracket_count == 0:
            end = i
            break

    if end == -1 and add_missing_right_bracket:
        # If no closing bracket is found, but we are allowed to add one
        text += "]"
        end = len(text) - 1
    elif end == -1:
        raise ValueError(
            "Incomplete list found and add_missing_right_bracket is False."
        )

    return text[start : end + 1]


def fix_json_missing_commas(json_str: str) -> str:
    # Example: adding missing commas, only after double quotes
    # Regular expression to find missing commas
    regex = r'(?<=[}\]"\'\d])(\s+)(?=[\{"\[])'

    # Add commas where missing
    fixed_json_str = re.sub(regex, r",\1", json_str)

    return fixed_json_str


def fix_json_escaped_single_quotes(json_str: str) -> str:
    # First, replace improperly escaped single quotes inside strings
    # json_str = re.sub(r"(?<!\\)\'", '"', json_str)
    # Fix escaped single quotes
    json_str = json_str.replace(r"\'", "'")
    return json_str


def parse_json_str_to_obj(json_str: str) -> Dict[str, Any]:
    r"""
    Parse a JSON string to a Python object.
    json_str: has to be a valid JSON string. Either {} or [].
    """
    json_str = json_str.strip()
    try:
        json_obj = json.loads(json_str)
        return json_obj
    except json.JSONDecodeError as e:
        # 2nd attemp after fixing the json string
        try:
            print("Trying to fix potential missing commas...")
            json_str = fix_json_missing_commas(json_str)
            print("Trying to fix scaped single quotes...")
            json_str = fix_json_escaped_single_quotes(json_str)
            print(f"Fixed JSON string: {json_str}")
            json_obj = json.loads(json_str)
            return json_obj
        except json.JSONDecodeError as e:
            # 3rd attemp using yaml
            try:
                import yaml

                # NOTE: parsing again with pyyaml
                #       pyyaml is less strict, and allows for trailing commas
                #       right now we rely on this since guidance program generates
                #       trailing commas
                print("Parsing JSON string with PyYAML...")
                json_obj = yaml.safe_load(json_str)
                return json_obj
            except yaml.YAMLError as e_yaml:
                raise ValueError(
                    f"Got invalid JSON object. Error: {e}. Got JSON string: {json_str}"
                )
            except NameError as exc:
                raise ImportError("Please pip install PyYAML.") from exc
