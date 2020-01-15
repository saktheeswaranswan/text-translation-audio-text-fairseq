#!/usr/bin/env python3 -u
#!/usr/bin/env python3 -u
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import torch

<<<<<<< HEAD
<<<<<<< HEAD
from fairseq import checkpoint_utils, options, progress_bar, utils
=======
from fairseq import checkpoint_utils, metrics, options, progress_bar, utils
>>>>>>> replace symlinks with actual files to prevent Windows CLI issues when building from source.
=======
from fairseq import checkpoint_utils, metrics, options, progress_bar, utils
=======
from fairseq import checkpoint_utils, options, progress_bar, utils
>>>>>>> 8573e5bb18e63c00e090f0c81bcbc613f262d0f2
>>>>>>> fix rebase.


def main(args, override_args=None):
    utils.import_user_module(args)

<<<<<<< HEAD
<<<<<<< HEAD
=======
    assert args.max_tokens is not None or args.max_sentences is not None, \
        'Must specify batch size either with --max-tokens or --max-sentences'

>>>>>>> replace symlinks with actual files to prevent Windows CLI issues when building from source.
=======
    assert args.max_tokens is not None or args.max_sentences is not None, \
        'Must specify batch size either with --max-tokens or --max-sentences'

=======
>>>>>>> 8573e5bb18e63c00e090f0c81bcbc613f262d0f2
>>>>>>> fix rebase.
    use_fp16 = args.fp16
    use_cuda = torch.cuda.is_available() and not args.cpu

    if override_args is not None:
        overrides = vars(override_args)
        overrides.update(eval(getattr(override_args, 'model_overrides', '{}')))
    else:
        overrides = None

    # Load ensemble
    print('| loading model(s) from {}'.format(args.path))
    models, model_args, task = checkpoint_utils.load_model_ensemble_and_task(
        [args.path],
        arg_overrides=overrides,
    )
    model = models[0]

    # Move models to GPU
    for model in models:
        if use_fp16:
            model.half()
        if use_cuda:
            model.cuda()

    # Print args
    print(model_args)

    # Build criterion
    criterion = task.build_criterion(model_args)
    criterion.eval()

    # Load valid dataset (we load training data below, based on the latest checkpoint)
    for subset in args.valid_subset.split(','):
        try:
            task.load_dataset(subset, combine=False, epoch=0)
            dataset = task.dataset(subset)
        except KeyError:
            raise Exception('Cannot find dataset: ' + subset)

        # Initialize data iterator
        itr = task.get_batch_iterator(
            dataset=dataset,
            max_tokens=args.max_tokens,
            max_sentences=args.max_sentences,
            max_positions=utils.resolve_max_positions(
                task.max_positions(),
                *[m.max_positions() for m in models],
            ),
            ignore_invalid_inputs=args.skip_invalid_size_inputs_valid_test,
            required_batch_size_multiple=args.required_batch_size_multiple,
            seed=args.seed,
            num_workers=args.num_workers,
        ).next_epoch_itr(shuffle=False)
        progress = progress_bar.build_progress_bar(
            args, itr,
            prefix='valid on \'{}\' subset'.format(subset),
            no_progress_bar='simple'
        )

        log_outputs = []
        for i, sample in enumerate(progress):
            sample = utils.move_to_cuda(sample) if use_cuda else sample
            _loss, _sample_size, log_output = task.valid_step(sample, model, criterion)
            progress.log(log_output, step=i)
            log_outputs.append(log_output)

<<<<<<< HEAD
<<<<<<< HEAD
        log_output = task.aggregate_logging_outputs(log_outputs, criterion)
=======
        with metrics.aggregate() as agg:
            task.reduce_metrics(log_outputs, criterion)
            log_output = agg.get_smoothed_values()
>>>>>>> replace symlinks with actual files to prevent Windows CLI issues when building from source.
=======
        with metrics.aggregate() as agg:
            task.reduce_metrics(log_outputs, criterion)
            log_output = agg.get_smoothed_values()
=======
        log_output = task.aggregate_logging_outputs(log_outputs, criterion)
>>>>>>> 8573e5bb18e63c00e090f0c81bcbc613f262d0f2
>>>>>>> fix rebase.

        progress.print(log_output, tag=subset, step=i)


def cli_main():
    parser = options.get_validation_parser()
    args = options.parse_args_and_arch(parser)

    # only override args that are explicitly given on the command line
    override_parser = options.get_validation_parser()
    override_args = options.parse_args_and_arch(override_parser, suppress_defaults=True)

    main(args, override_args)


if __name__ == '__main__':
    cli_main()
