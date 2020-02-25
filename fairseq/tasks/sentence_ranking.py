# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os

import numpy as np

from fairseq.data import (
    ConcatSentencesDataset,
    data_utils,
    Dictionary,
    IdDataset,
    NestedDictionaryDataset,
    NumSamplesDataset,
    NumelDataset,
    PrependTokenDataset,
    RawLabelDataset,
    RightPadDataset,
    SortDataset,
    TruncateDataset,
)
from fairseq.tasks import FairseqTask, register_task


logger = logging.getLogger(__name__)


@register_task('sentence_ranking')
class SentenceRankingTask(FairseqTask):
    """
    Ranking task on multiple sentences.

    Args:
        dictionary (Dictionary): the dictionary for the input of the task
    """

    @staticmethod
    def add_args(parser):
        """Add task-specific arguments to the parser."""
        parser.add_argument('data', metavar='FILE',
                            help='file prefix for data')
        parser.add_argument('--num-classes', type=int,
                            help='number of sentences to be ranked')
        parser.add_argument('--init-token', type=int,
                            help='add token at the beginning of each batch item')
        parser.add_argument('--separator-token', type=int,
                            help='add separator token between inputs')
        parser.add_argument('--no-shuffle', action='store_true')
        parser.add_argument('--truncate-sequence', action='store_true',
                            help='Truncate sequence to max_positions')
        parser.add_argument('--max-option-length', type=int,
                            help='max length for each option')

    def __init__(self, data, num_classes, init_token, separator_token, no_shuffle, truncate_sequence, max_option_length,
                 dataset_impl, seed, dictionary):
        super().__init__()
        self.data = data
        self.num_classes = num_classes
        self.init_token = init_token
        self.separator_token = separator_token
        self.no_shuffle = no_shuffle
        self.truncate_sequence = truncate_sequence
        self.max_option_length = max_option_length
        self.dataset_impl = dataset_impl
        self.seed = seed
        self.dictionary = dictionary

    @classmethod
    def load_dictionary(cls, args, filename, source=True):
        """Load the dictionary from the filename

        Args:
            filename (str): the filename
        """
        dictionary = Dictionary.load(filename)
        dictionary.add_symbol('<mask>')
        return dictionary

    @classmethod
    def setup_task(cls, args, **kwargs):
        assert args.criterion == 'sentence_ranking', \
            'Must set --criterion=sentence_ranking'

        # load data dictionary
        data_dict = cls.load_dictionary(
            args,
            os.path.join(args.data, 'input0', 'dict.txt'),
            source=True,
        )
        logger.info('[input] dictionary: {} types'.format(len(data_dict)))
        return SentenceRankingTask(
            args.data, args.num_classes, args.init_token, args.separator_token, args.no_shuffle, args.truncate_sequence,
            args.max_option_length, args.dataset_impl, args.seed, data_dict
        )

    def load_dataset(self, split, combine=False, **kwargs):
        """Load a given dataset split (e.g., train, valid, test)."""

        def get_path(type, split):
            return os.path.join(self.data, type, split)

        def make_dataset(type, dictionary):
            split_path = get_path(type, split)

            dataset = data_utils.load_indexed_dataset(
                split_path,
                self.source_dictionary,
                self.dataset_impl,
                combine=combine,
            )
            return dataset

        input0 = make_dataset('input0', self.source_dictionary)
        input_options = [
            make_dataset(
                'input{idx}'.format(idx=idx + 1),
                self.source_dictionary
            )
            for idx in range(self.num_classes)
        ]

        if self.separator_token is not None:
            input0 = PrependTokenDataset(input0, self.separator_token)

        src_tokens = []
        for input_option in input_options:
            if self.init_token is not None:
                input_option = PrependTokenDataset(input_option, self.init_token)
            if self.max_option_length is not None:
                input_option = TruncateDataset(input_option, self.max_option_length)
            src_token = ConcatSentencesDataset(input_option, input0)
            if self.truncate_sequence:
                src_token = TruncateDataset(src_token, self.max_positions)
            src_tokens.append(src_token)

        with data_utils.numpy_seed(self.seed):
            shuffle = np.random.permutation(len(src_tokens[0]))

        dataset = {
            'id': IdDataset(),
            'nsentences': NumSamplesDataset(),
            'ntokens': NumelDataset(src_tokens[0], reduce=True),
        }

        for src_token_idx in range(len(src_tokens)):
            dataset.update(
                {
                    'net_input{idx}'.format(idx=src_token_idx+1): {
                        'src_tokens': RightPadDataset(
                            src_tokens[src_token_idx],
                            pad_idx=self.source_dictionary.pad(),
                        ),
                        'src_lengths': NumelDataset(src_tokens[src_token_idx], reduce=False),
                    }
                }
            )

        label_path = '{}.label'.format(get_path('label', split))
        if os.path.exists(label_path):
            with open(label_path) as h:
                dataset.update(
                    target=RawLabelDataset([
                        int(x.strip()) for x in h.readlines()
                    ])
                )

        nested_dataset = NestedDictionaryDataset(
            dataset,
            sizes=[np.maximum.reduce([src_token.sizes for src_token in src_tokens])],
        )

        if self.no_shuffle:
            dataset = nested_dataset
        else:
            dataset = SortDataset(
                nested_dataset,
                # shuffle
                sort_order=[shuffle],
            )

        logger.info("Loaded {0} with #samples: {1}".format(split, len(dataset)))

        self.datasets[split] = dataset
        return self.datasets[split]

    def build_model(self, args):
        from fairseq import models
        model = models.build_model(args, self)

        model.register_classification_head(
            getattr(args, 'ranking_head_name', 'sentence_classification_head'),
            num_classes=1,
        )

        return model

    def max_positions(self):
        return self.max_positions

    @property
    def source_dictionary(self):
        return self.dictionary

    @property
    def target_dictionary(self):
        return self.dictionary
