from collections import defaultdict
from itertools import groupby
from operator import itemgetter
from typing import List, Dict, Any, Tuple
from datasets import Dataset
from tqdm import tqdm
import numpy as np
from transformers import EvalPrediction
from primeqa.mrc.processors.postprocessors.extractive import ExtractivePostProcessor
from primeqa.mrc.data_models.target_type import TargetType


class NaturalQuestionsPostProcessor(ExtractivePostProcessor):
    """
    Post processor for NQ.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def process(self, examples: Dataset, features: Dataset, predictions: Tuple[np.ndarray, np.ndarray, np.ndarray]):
        """
        Adjust answer start/end positions to original document html.
        The start/end positions return from super().process() point to the context of document tokens.
        """
        predictions = super().process(examples, features, predictions)

        for example in examples:
            example_id = example['example_id']
            for pred in predictions[example_id]:
                start_position = pred['span_answer']['start_position']
                end_position = pred['span_answer']['end_position']
                start_token_position = example['context_char_to_token'][start_position]
                end_token_position = example['context_char_to_token'][end_position - 1]
                new_start_position = example['document_tokens']['start_byte'][start_token_position]
                new_end_position = example['document_tokens']['end_byte'][end_token_position]
                pred['span_answer']['start_position'] = new_start_position
                pred['span_answer']['end_position'] = new_end_position

                pred['passage_index'] = -1
                passage_candidates = example['passage_candidates']
                for context_idx in range(len(passage_candidates['start_positions'])):
                    passage_start_position = passage_candidates['start_positions'][context_idx]
                    passage_end_position = passage_candidates['end_positions'][context_idx]
                    if passage_start_position <= new_start_position <= new_end_position <= passage_end_position:
                        pred['passage_index'] = context_idx
                        break

        return predictions


    def prepare_examples_as_references(self, examples: Dataset) -> List[Dict[str, Any]]:
        """
        Prepare reference for each example.
        document_plaintext and question are not included to comply with the definition of NQLabel in
        primeqa.mrc.metrics.nq_f1.eval_utils
        """
        references = []
        for example_idx in range(examples.num_rows):
            example = examples[example_idx]
            n_annotators = len(example['target']['start_positions'])
            label = {
                'start_position': example['target']['start_positions'],
                'end_position': example['target']['end_positions'],
                'passage_index': example['target']['passage_indices'],
                'yes_no_answer': list(map(TargetType.from_bool_label, example['target']['yes_no_answer'])),  # TODO: decide on schema type for bool ans
                'example_id': [example['example_id']] * n_annotators,
                'language': [example['language']] * n_annotators,
            }
            references.append(label)
        return references
