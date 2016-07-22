# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import random

# a list of congratulations messages to be issued when the learner solves a task
congratulations = ['good job.',
                   'bravo.',
                   'congratulations.',
                   'nice work.',
                   'correct.']
# a list of congratulations messages to be issued when the learner fails a task
failed = ['wrong!',
          'wrong.',
          'you failed!',
          'incorrect.']

# handy list with word transcriptions of the integers from 0 to 10
numbers_in_words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six',
                    'seven', 'eight', 'nine', 'ten']


def number_to_string(num):
    '''
    Returns a string version of a number, randomly picking between
    letters and numbers.
    '''
    if num <= len(numbers_in_words) and random.randint(0, 1) == 1:
        return numbers_in_words[num]
    else:
        return str(num)


def string_to_number(n):
    if n in numbers_in_words:
        return numbers_in_words.index(n)
    else:
        return int(n)