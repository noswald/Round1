import random
import re
import string

from core.task import on_message, on_start, on_timeout
from core.task import Task
from tasks.good_ai.task_generator import TaskGenerator

ARBITRARY_SUCCESS_NUMBER = 20


class MicroBase(Task):
    reg_answer_end = r'.'
    MAXIMUM_ANSWER_LEN = 1000
    failed_task_tolerance = 1.0

    def __init__(self, world=None):
        super(MicroBase, self).__init__(world=world, max_time=3000)
        self.skip_task_separator = True
        self.new_task_instance()

    @staticmethod
    def get_task_generator():
        pass

    def agent_solved_instance(self):
        return False

    def question_answered(self, is_correct):
        self.questions_asked += 1

    def get_original_question(self, question):
        return self.tasker.get_original_question(question)

    def new_task_instance(self):
        self.tasker = self.get_task_generator()
        self.questions_asked = 0
        self.consecutive_reward = 0
        self.task_instance_successful = True
        self.max_questions_nr = None

    def check_if_task_instance_solved(self):
        solved = self.agent_solved_instance()
        if solved is False:  # agent failed the task instance
            self.task_instance_successful = False
            self.max_questions_nr = self.questions_asked * self.failed_task_tolerance
        elif solved is True:    # agent managed to solve the task instance
            self.new_task_instance()
        if self.max_questions_nr and self.questions_asked >= self.max_questions_nr:  # agent used up all the extra time
            self.new_task_instance()

    def provide_reward(self, reward):
        if reward > 0:
            self.consecutive_reward += 1
        else:
            self.consecutive_reward = 0
        self.set_immediate_reward(reward)

    def provide_feedback(self, correct):
        feedback_text = self.tasker.get_feedback_text(correct, self.question)
        self.set_message(feedback_text)

    def preprocess_answer(self, answer):
        answer = answer.strip()
        if answer == '':
            answer = ' '
        return answer

    @on_start()
    def give_instructions(self, event):
        self.question, self.check_answer = self.tasker.get_task_instance()
        self.set_message(self.question)

    @on_message(r'.')
    def check_response(self, event):
        if not self._env.is_silent():
            if not event.message[-1] == ' ':
                self.set_immediate_reward(-1)
            return
        if not self._answer_ended(event.message):
            return

        answer = self.preprocess_answer(event.message)
        finished, correct, reward = self.tasker.check_answer(answer, self.question)
        self.provide_reward(reward)
        self.provide_feedback(correct)
        self.question_answered(correct)
        self.check_if_task_instance_solved()

    @on_timeout()
    def end_task_instance(self, event):
        self.set_result(self.task_instance_successful, provide_result_as_reward=False)
        self.new_task_instance()

    @staticmethod
    def is_prefix(answer, correct_answer):
        if len(answer) >= len(correct_answer):
            return False
        return correct_answer.startswith(answer)

    def _answer_ended(self, message):
        return not (re.search(self.reg_answer_end, message) is None)


class TransparentTaskMixin(object):
    '''
    Mixin for Micro tasks, which - once understood - can be solved perfectly from the 1st step
    '''

    def agent_solved_instance(self):
        if self.questions_asked >= ARBITRARY_SUCCESS_NUMBER:
            return self.consecutive_reward == self.questions_asked


class Micro1Task(MicroBase):

    def __init__(self):
        self.alphabet = string.ascii_letters + string.digits + ' ,.!;?-'
        super(Micro1Task, self).__init__()
        self.expected_reward = 0
        self.should_know = False
        self.remaining_options = len(self.alphabet)

    def question_answered(self, is_correct):
        super(Micro1Task, self).question_answered(is_correct)
        if self.should_know:
            self.expected_reward += 1
        if is_correct or self.remaining_options == 0:
            self.should_know = True
        self.remaining_options -= 1

    def agent_solved_instance(self):
        if self.expected_reward >= ARBITRARY_SUCCESS_NUMBER:
            return self.consecutive_reward >= self.expected_reward

    def get_task_generator(self):
        alphabet = self.alphabet
        correct_answer = random.choice(alphabet)

        def micro1_question(self):
            return random.choice(alphabet), correct_answer
        return TaskGenerator(micro1_question)


def random_string_from(length, subset):
    return "".join(random.choice(subset) for _ in range(length))


def random_strings_from(charset, nr_of_strings, string_len_options=None, append=''):
    string_len_options = string_len_options or [1]
    result = []
    for _ in range(nr_of_strings):
        answer_len = random.choice(string_len_options)
        answer = random_string_from(answer_len, charset)
        result.append(answer + append)
    return result


class MicroMappingTask(MicroBase):

    task_gen_kwargs = {}

    def __init__(self):
        super(MicroMappingTask, self).__init__()
        all_options = self._get_mapping_options()
        self.known_mapping = {x: len(all_options[x]) for x in all_options.keys()}
        print(self.known_mapping)
        self.should_know = False
        self.expected_reward = 0

    def _get_mapping_options(self):
        '''
        If the mapping task is standard mapping (one element to some other element), it only has to implement this method.
        MicroMappingTask then handles the creation of mapping and implementing the mechanism for checking the agent performance.
        But if the mapping task has some special needs (e.g. mapping each element to unique thing) it has to implement _get_mapping
        and agent_solved_instance by itself
        '''
        return {}

    def _get_mapping(self):
        '''
        This just picks one of the possible mappings from _get_mapping_options
        By default, there can be more elements mapped onto the same thing
        '''
        mapping_options = self._get_mapping_options()
        result = {x: random.choice(y) for x, y in mapping_options.items()}
        return result

    def agent_solved_instance(self):
        if self.expected_reward >= ARBITRARY_SUCCESS_NUMBER:
            return self.consecutive_reward >= self.expected_reward

    def question_answered(self, is_correct):
        super(MicroMappingTask, self).question_answered(is_correct)
        if len(self.known_mapping) == 0:    # not all Mapping tasks use the all_mapping_options concept
            return
        if is_correct:
            self.known_mapping[self.question] = 1
        else:
            self.known_mapping[self.question] -= 1
        if self.should_know:
            self.expected_reward += 1
        if all(x == 1 for x in self.known_mapping.values()):
            self.should_know = True

    def get_task_generator(self):
        mapping = self._get_mapping()

        def multigen(d):
            while True:
                k = list(d.keys()) * len(d.keys())
                random.shuffle(k)
                for i in k:
                    yield i
        gen = multigen(mapping)

        def micro_mapping_question(self):
            def micro_mapping_reward(answer, question):
                key = self.get_original_question(question)
                if len(answer) > 0 and MicroBase.is_prefix(answer, mapping[key]):
                    return None, 0
                correct = answer == mapping[key]
                return correct, 1 if correct else -1
            return next(gen), micro_mapping_reward
        return TaskGenerator(micro_mapping_question, **self.task_gen_kwargs)

    # this could be solved by less code, but I chose the explicit way
    def _get_simple_feedback_provider(self, mapping):
        def feedback_provider(is_correct, question):
            key = self.get_original_question(question)
            return mapping[key]
        return feedback_provider

    def _get_prepend_feedback_provider(self, mapping, prepend_set, prepend_len_options=None):
        prepend_len_options = prepend_len_options or [1]

        def feedback_provider(is_correct, question):
            key = self.get_original_question(question)
            prepend_len = random.choice(prepend_len_options)
            prepend = random_string_from(prepend_len, prepend_set)
            return prepend + mapping[key]
        return feedback_provider


class Micro2Task(MicroMappingTask):

    def __init__(self):
        super(Micro2Task, self).__init__()
        self.should_know = False
        self.expected_reward = 0
        self.remaining_options = len(string.ascii_lowercase)

    def agent_solved_instance(self):
        if self.expected_reward >= ARBITRARY_SUCCESS_NUMBER:
            return self.consecutive_reward >= self.expected_reward

    def question_answered(self, is_correct):
        super(Micro2Task, self).question_answered(is_correct)
        if self.should_know:
            self.expected_reward += 1
        if (is_correct and self.question in string.ascii_lowercase) or self.remaining_options == 0:
            self.should_know = True

    def _get_mapping(self):
        correct_answer = random.choice(string.ascii_lowercase)
        mapping = {x: correct_answer for x in string.ascii_lowercase}
        for c in ' !":?.,;':
            mapping[c] = c
        return mapping


class Micro3Task(MicroMappingTask):

    def _get_mapping_options(self):
        return {x: list(string.ascii_lowercase) for x in string.ascii_lowercase}

    def _get_mapping(self):
        permutation = ''.join(random.sample(string.ascii_lowercase, len(string.ascii_lowercase)))
        mapping = dict(zip(string.ascii_lowercase, permutation))
        for c in ' !":?.,;':
            mapping[c] = c
        return mapping


class Micro4Task(TransparentTaskMixin, MicroMappingTask):

    def _get_mapping(self):
        alphabet = string.ascii_lowercase + ' !":?.,;'
        mapping = dict(zip(alphabet, alphabet))
        return mapping


class Micro5Sub1Task(MicroMappingTask):
    task_gen_kwargs = {}

    def _get_mapping(self):
        numbers = '0123456789'
        permutation = ''.join(random.sample(numbers, len(numbers)))
        mapping = dict(zip(numbers, permutation))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub2Task(Micro5Sub1Task):
    task_gen_kwargs = {'feedback_sep': '!'}


class Micro5Sub3Task(Micro5Sub1Task):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}


# TODO: example (also 5.5 and 5.6) shows one space between question and
# the feedback, but the description does not mention it - this is version
# without the space
class Micro5Sub4Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random_string_from(2, numbers) for x in numbers}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub5Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random.choice(numbers) + '.' for x in numbers}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub6Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random.choice(numbers) + '.' for x in numbers}

        def feedback_provider(is_correct, question):
            key = self.get_original_question(question)
            if is_correct:
                return mapping[key][:-1]    # remove trailing dot
            return mapping[key]
        self.task_gen_kwargs['provide_feedback'] = feedback_provider
        return mapping


class Micro5Sub7Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        answers = random_strings_from(numbers, len(numbers), [1, 2], '.')
        mapping = dict(zip(numbers, answers))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub8Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, [2])
        mapping = {x: random.choice(numbers) + '.' for x in questions}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub9Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, [1, 2])
        mapping = {x: random.choice(numbers) + '.' for x in questions}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


# TODO: should be the ignored part be always the same for the same inputs or can it change? - this version changes it
class Micro5Sub10Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random.choice(numbers) + '.' for x in numbers}

        self.task_gen_kwargs['provide_feedback'] = self._get_prepend_feedback_provider(mapping, numbers)
        return mapping


class Micro5Sub11Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random.choice(numbers) + '.' for x in numbers}

        def feedback_provider(is_correct, question):
            key = self.get_original_question(question)
            do_prepend = random.choice([True, False])
            if do_prepend:
                prepend = random.choice(numbers)
            else:
                prepend = ''
            return prepend + mapping[key]
        self.task_gen_kwargs['provide_feedback'] = feedback_provider
        return mapping


# stems from 5.7
# TODO: description says "either 3 or 4 or 5 chars. Shown example for 3
# chars". So will it be always the same size of feedback for on task
# instance? Or can it be mixed? - this version is mixed
# same question for 5.13, 5.14, 5.15, 5.16, 5.17 and 5.18
class Micro5Sub12Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        answers = random_strings_from(numbers, len(numbers), [3, 4, 5], '.')
        mapping = dict(zip(numbers, answers))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


# stems from 5.9
class Micro5Sub13Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, [3, 4, 5])
        mapping = {x: random.choice(numbers) + '.' for x in questions}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


# stems from 5.12
class Micro5Sub14Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        mapping = {x: random.choice(numbers) + '.' for x in numbers}

        self.task_gen_kwargs['provide_feedback'] = self._get_prepend_feedback_provider(mapping, numbers, [2, 3, 4])
        return mapping


class Micro5Sub15Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        answers = random_strings_from(numbers, len(numbers), range(1, 6), '.')
        mapping = dict(zip(numbers, answers))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub16Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, range(1, 6))
        mapping = {x: random.choice(numbers) + '.' for x in questions}

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro5Sub17Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, range(1, 6))
        answers = random_strings_from(numbers, len(questions), range(1, 6), '.')
        mapping = dict(zip(questions, answers))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


# stems from 5.17
class Micro5Sub18Task(MicroMappingTask):
    task_gen_kwargs = {'input_sep': '.', 'feedback_sep': '!'}

    def _get_mapping(self):
        numbers = '0123456789'
        nr_questions = 10
        questions = random_strings_from(numbers, nr_questions, range(1, 11))
        answers = random_strings_from(numbers, len(questions), range(1, 11), '.')
        mapping = dict(zip(questions, answers))

        self.task_gen_kwargs['provide_feedback'] = self._get_simple_feedback_provider(mapping)
        return mapping


class Micro6Sub1Task(MicroBase):

    def get_task_generator(self):
        def micro6_1_question(self):
            correct_answer = random.choice(string.ascii_lowercase) + '.'
            question = "say: {}".format(correct_answer)

            def micro6_1_feedback(is_correct, question):
                reaction = "correct" if is_correct else "false"
                return reaction + '. ' + correct_answer
            return question, [correct_answer], micro6_1_feedback
        return TaskGenerator(micro6_1_question, '', None, ';')


class Micro6Sub2Task(MicroBase):

    def get_task_generator(self):
        valid_words = ["hello", "hi", "ahoy"]

        def micro6_2_question(self):
            word = random.choice(valid_words) + '.'
            question = "say: {}".format(word)

            def micro6_2_feedback(is_correct, question):
                reaction = "correct" if is_correct else "false"
                return reaction + '. ' + word
            return question, [word], micro6_2_feedback
        return TaskGenerator(micro6_2_question, '', None, ';')


class Micro6Sub3Task(MicroBase):

    def get_task_generator(self):
        valid_words = ["hello", "hi", "ahoy", "world", "agent", "ai"]

        def micro6_3_question(self):
            sentence = random.choice(valid_words) + random.choice(valid_words) + '.'
            question = "say: {}".format(sentence)

            def micro6_3_feedback(is_correct, question):
                reaction = "correct" if is_correct else "false"
                return reaction + '. ' + sentence
            return question, [sentence], micro6_3_feedback
        return TaskGenerator(micro6_3_question, '', None, ';')


class Micro7Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro7_question(self):
            alphabet = string.ascii_lowercase
            sentence = "{}{}{}{}{}.".format(' ' * random.randint(0, 6), random.choice(alphabet), ' ' * random.randint(0, 6),
                                            random.choice(alphabet), ' ' * random.randint(0, 6))
            question = "say: {}".format(sentence)
            sentence = re.sub(' +', ' ', sentence).strip()

            def micro7_feedback(is_correct, question):
                reaction = "correct" if is_correct else "false"
                return reaction + '!' + sentence
                print("sentence: ".format(sentence))
            return question, [sentence], micro7_feedback

        return TaskGenerator(micro7_question, '', None, ';')


class Micro8Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro8_question(self):
            valid_words = ["hello", "hi", "ahoy", "mono"]
            word = random.choice(valid_words) + '.'
            question = "spell: {}".format(word)
            sentence = " ".join(word)

            def micro8_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                return reaction + '! ' + sentence
            return question, [sentence], micro8_feedback
        return TaskGenerator(micro8_question, '', None, ';')


class Micro9Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro9_question(self):
            valid_words = ["hello", "hi", "ahoy", "mono"]
            n = random.randint(2, 3)
            questions = []
            words = []
            for i in range(0, n):
                word = random.choice(valid_words)
                words.append(word)
                questions.append('say: {}'.format(word))
            question = ' '.join(questions)
            question += '.'
            sentence = ' '.join(words)
            sentence += '.'

            def micro9_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            return question, [sentence], micro9_feedback
        return TaskGenerator(micro9_question, '', None, ';')


class Micro10Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro10_question(self):
            actions = ['reverse', 'concatenate', 'interleave']
            action = random.choice(actions)
            valid_words = ["ab", "ac", "ad", "bc", "bd", "cd"]
            questions = []
            words = []
            for i in range(0, 2):
                word = random.choice(valid_words)
                words.append(word)
                questions.append('say: {}'.format(word))
            question = ' '.join(questions)
            question += ' '
            question += action
            question += ':.'
            if action == 'reverse':
                words.reverse()
                sentence = ' '.join(words)
            elif action == 'concatenate':
                sentence = ''.join(words)
            else:
                sentence = [val for pair in zip(words[0], words[1]) for val in pair]
                sentence = ''.join(sentence)
            sentence += '.'

            def micro10_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            return question, [sentence], micro10_feedback
        return TaskGenerator(micro10_question, '', None, ';')


class Micro11Task(MicroBase):
    reg_answer_end = r'\.'

    @staticmethod
    def string_special_union(str1, str2):
        if str1.find(str2) >= 0:
            return str1
        return str1 + str2

    @staticmethod
    def string_special_exclude(str1, str2):
        return str1.replace(str2, '')

    def get_task_generator(self):
        def micro11_question(self):
            actions = ['union', 'exclude']
            action = random.choice(actions)
            valid_words = ["abc", "acd", "adc", "bcd", "bda", "cdb"]
            valid_second_words = ["a", "b", "c", "d"]
            word = random.choice(valid_words)
            second_word = random.choice(valid_second_words)
            question = 'say: {} say: {} {}:.'.format(word, second_word, action)
            if action == 'union':
                sentence = Micro11Task.string_special_union(word, second_word)
            else:
                sentence = Micro11Task.string_special_exclude(word, second_word)
            sentence += '.'

            def micro11_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            return question, [sentence], micro11_feedback
        return TaskGenerator(micro11_question, '', None, ';')


class Micro12Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro12_question(self):
            alphabet = string.ascii_lowercase
            idx = random.randint(0, len(alphabet) - 2)
            question = 'after {} comes what:.'.format(alphabet[idx])
            sentence = alphabet[idx + 1]
            sentence += '.'

            def micro12_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            return question, [sentence], micro12_feedback
        return TaskGenerator(micro12_question, '', None, ';')


class Micro13Task(MicroBase):
    reg_answer_end = r'\.'
    m7 = Micro7Task()
    m8 = Micro8Task()
    m9 = Micro9Task()
    m10 = Micro10Task()
    m11 = Micro11Task()
    m12 = Micro12Task()

    @on_start()
    def give_instructions(self, event):
        self.tasker = self.get_task_generator()
        super(Micro13Task).give_instructions(self, event)

    def get_task_generator(self):
        tasks = [self.m9, self.m10, self.m11]
        task = random.choice(tasks)
        return task.get_task_generator()


class Micro15Sub1Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro15_question(self):
            def micro15_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            action = random.randint(1, 4)
            words = list('abcde')
            # and
            if action == 1:
                word1 = random.choice(words)
                word2 = random.choice(words)
                question = ' say: {} and {}.'.format(word1, word2)
                sentence1 = '{}{}.'.format(word1, word2)
                sentence2 = '{}{}.'.format(word2, word1)
                sentence = random.choice([sentence1, sentence2])
                return question, [sentence1, sentence2], micro15_feedback
            # or
            elif action == 2:
                word1 = random.choice(words)
                word2 = random.choice(words)
                question = ' say: {} or {}.'.format(word1, word2)
                sentence = '{}.'.format(random.choice([word1, word2]))

                def or_reward(answer, question=''):
                    correct = answer.find(word1) >= 0 or answer.find(word2) >= 0
                    return correct, 1 if correct else -1
                return question, or_reward, micro15_feedback
            # anything and not
            elif action == 3:
                word1 = 'anything'
                word2 = random.choice(words)
                words.remove(word2)
                question = ' say: {} and not {}.'.format(word1, word2)
                sentence = random.choice(words)

                def anything_and_not_reward(answer, question=''):
                    correct = answer.find(word2) < 0
                    return correct, 1 if correct else -1
                return question, anything_and_not_reward, micro15_feedback
            # or but not
            else:
                word1 = random.choice(words)
                words.remove(word1)
                word2 = random.choice(words)
                words.remove(word2)
                word3 = random.choice([word1, word2, random.choice(words)])
                question = ' say: {} or {} but not {}.'.format(word1, word2, word3)
                correct_word = [word1, word2]
                if word3 in correct_word:
                    correct_word.remove(word3)
                sentence = random.choice(correct_word)

                def or_but_not_reward(answer, question=''):
                    correct = answer.find(word3) < 0 and (answer.find(word2) >= 0 or answer.find(word1) >= 0)
                    return correct, 1 if correct else -1
                return question, or_but_not_reward, micro15_feedback
        return TaskGenerator(micro15_question, '', None, ';')


class Micro15Sub2Task(MicroBase):
    reg_answer_end = r'\.'

    def get_task_generator(self):
        def micro15sub2_question(self):
            def micro15sub2_feedback(is_correct, question):
                reaction = "good job" if is_correct else "wrong"
                if not is_correct:
                    return reaction + '! ' + sentence
                else:
                    return reaction + '! '
            alphabet = 'abcdefghi'
            actions = ['or', 'and']
            action = random.choice(actions)
            operands = random.randint(2, 4)
            words = []
            for i in range(operands):
                word_length = random.randint(1, 3)
                words.append(''.join(random.sample(alphabet, word_length)))
            clause = (' ' + action + ' ').join(words)
            if action == 'or':
                no_words = random.sample(words, random.randint(1, operands - 1))
                sentence = random.choice([item for item in words if item not in no_words])
                sentence += '.'

                def or_but_not_reward(answer, question=''):
                    correct = any(answer.find(word) >= 0 for word in words) \
                        and all(answer.find(no_word) < 0 for no_word in no_words)
                    return correct, 1 if correct else -1
                question = 'say: ' + clause + ' and not ' + ' and '.join(no_words) + '.'
                return question, or_but_not_reward, micro15sub2_feedback
            else:
                sentence = ''.join(words)
                sentence += '.'
                question = 'say: ' + clause + '.'
                return question, sentence, micro15sub2_feedback

        return TaskGenerator(micro15sub2_question, '', None, ';')
