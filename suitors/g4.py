from typing import Dict
from collections import Counter
import math

from flowers import Bouquet, Flower, FlowerSizes, FlowerColors, FlowerTypes
from suitors.base import BaseSuitor
from random import shuffle, choice, randint
import numpy as np
from utils import flatten_counter
from constants import MAX_BOUQUET_SIZE


class Suitor(BaseSuitor):
    def __init__(self, days: int, num_suitors: int, suitor_id: int):
        """
        :param days: number of days of courtship
        :param num_suitors: number of suitors, including yourself
        :param suitor_id: unique id of your suitor in range(num_suitors)
        """
        super().__init__(days, num_suitors, suitor_id, name='g4')
        self.remaining_turns = days
        all_ids = np.arange(num_suitors)
        self.recipient_ids = all_ids[all_ids != suitor_id]
        self.to_be_tested = self.generate_tests()
        self.train_feedback = np.zeros((len(self.recipient_ids), 6, 4, 3))  # feedback score from other recipients
        self.last_bouquet = None  # bouquet we gave out from the last turn

        self.size_mapping = self.generate_map(FlowerSizes)
        self.color_mapping = self.generate_map(FlowerColors)
        self.type_mapping = self.generate_map(FlowerTypes)
        self.best_arrangement = self.generate_random_bouquet()
        self.best_arrangement_size_vec, self.best_arrangement_color_vec, self.best_arrangement_type_vec = \
        self.get_bouquet_score_vectors(self.best_arrangement)

    def generate_random_flower(self):
        return Flower(
            size = choice(list(FlowerSizes)),
            color = choice(list(FlowerColors)),
            type = choice(list(FlowerTypes)), 
        )

    def generate_random_bouquet(self):
        return [self.generate_random_flower() for _ in range(randint(1,MAX_BOUQUET_SIZE))]

    def get_bouquet_score_vectors(self, bouquet_vect):
        size_vec = [0] * len(FlowerSizes)
        color_vec = [0] * len(FlowerColors)
        type_vec = [0] * len(FlowerTypes)
        for flower in bouquet_vect:
            size_vec[flower.size.value] += 1
            color_vec[flower.color.value] += 1
            type_vec[flower.type.value] += 1

        return size_vec, color_vec, type_vec

    def compute_cosine_sim(self, v1, v2):
        # v1 and v2 are all positive numbers, so bounded from 0 to 1 
        return (v1 @ v2.T) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    def compute_euc_dist(self, v1, v2):
        # can make higher norm to increase steepness?
        return np.linalg.norm(np.array(v1) - np.array(v2))

    def compute_distance_heuristic(self, v1,v2):
        # v1 and v2 bounded from 0 to inf
        # need a cutoff to guarantee 0 score is possible. (e.g, assume we add distances together)
        # worst case scenario, theoretically the 
        # smallest maximum distance is assume the optimal bq is 12 flowers distributed amongst all attributes:
        # e.g, [4,4,4], [6,6], [3,3,3,3]
        # then according to our scoring heuristic, the 12 - min(vector) has to result in 0 (otherwise, it is possible
        # that no bq can result in a zero score.
        most_even_dist = math.floor(12/len(v1))
        threshold_vect = [0] * len(v1)
        threshold_vect[0] = 12
        THRESHOLD = 1 / (
            np.linalg.norm(
                np.array(threshold_vect)-
                np.array([most_even_dist] * len(v1))
            ) + 1
        ) 
        dist =  1 / (self.compute_euc_dist(v1,v2) + 1)
        return dist if dist > THRESHOLD else 0


    def generate_tests(self):
        to_be_tested = {}
        # TODO can set up a ratio for different variables that ensure each variable is getting tested within #days
        for recipient_id in self.recipient_ids:
            to_be_tested[str(recipient_id)] = []
            to_be_tested[str(recipient_id)].append([fc for fc in FlowerColors])
            to_be_tested[str(recipient_id)].append([ft for ft in FlowerTypes])
            to_be_tested[str(recipient_id)].append([fs for fs in FlowerSizes])

        return to_be_tested

    def generate_map(self, flower_enum):
        sizes = [n.value for n in flower_enum]
        shuffle(sizes)
        mapping = {}
        for idx, name in enumerate(flower_enum):
            mapping[name] = sizes[idx]
        return mapping

    def best_bouquet(self):
        best_size = (sorted([(key, value) for key, value in self.size_mapping.items()], key=lambda x: x[1]))[-1][0]
        best_color = (sorted([(key, value) for key, value in self.color_mapping.items()], key=lambda x: x[1]))[-1][0]
        best_type = (sorted([(key, value) for key, value in self.type_mapping.items()], key=lambda x: x[1]))[-1][0]
        best_flower = Flower(
            size=best_size,
            color=best_color,
            type=best_type
        )
        return Bouquet({best_flower: 1})

    def prepare_bouquets(self, flower_counts: Dict[Flower, int]):
        """
        :param flower_counts: flowers and associated counts for for available flowers
        :return: list of tuples of (self.suitor_id, recipient_id, chosen_bouquet)
        the list should be of length len(self.num_suitors) - 1 because you should give a bouquet to everyone
         but yourself

        To get the list of suitor ids not including yourself, use the following snippet:

        all_ids = np.arange(self.num_suitors)
        recipient_ids = all_ids[all_ids != self.suitor_id]
        """
        self.remaining_turns -= 1
        bouquet_for_all = []  # return value
        flower_info = self._flatten_flower_info(flower_counts)

        # if self.remaining_turns == 1:  # TODO second-to-last-day: testing phase
        #     pass

        if self.remaining_turns == 0:  # last day: final round

            # find highest score setup for each recipient
            max_args = []
            max_scores = []
            for r_ind in range(len(self.recipient_ids)):
                max_arg = None
                max_score = 0
                for c_ind in range(6):
                    for t_ind in range(4):
                        for s_ind in range(3):
                            if self.train_feedback[r_ind][c_ind][t_ind][s_ind] > max_score:
                                max_arg = (c_ind, t_ind, s_ind)
                                max_score = self.train_feedback[r_ind][c_ind][t_ind][s_ind]
                max_args.append(max_arg)
                max_scores.append(max_score)
            sorted_max_args = np.argsort(max_scores)[::-1]
            max_args = [max_args[max_arg] for max_arg in sorted_max_args]

            # random bouquets for everyone by default
            bouquet_for_all = []
            for r_ind in range(len(self.recipient_ids)):
                recipient_id = self.recipient_ids[r_ind]

                remaining_flowers = flower_counts.copy()
                num_remaining = sum(remaining_flowers.values())
                size = int(np.random.randint(0, min(MAX_BOUQUET_SIZE, num_remaining) + 1))
                if size > 0:
                    chosen_flowers = np.random.choice(flatten_counter(remaining_flowers), size=(size,), replace=False)
                    chosen_flower_counts = dict(Counter(chosen_flowers))
                    for k, v in chosen_flower_counts.items():
                        remaining_flowers[k] -= v
                        assert remaining_flowers[k] >= 0
                else:
                    chosen_flower_counts = dict()
                chosen_bouquet = Bouquet(chosen_flower_counts)
                bouquet_for_all.append([self.suitor_id, recipient_id, chosen_bouquet])

            # # give flowers if resources are available
            # for max_arg_ind in range(len(max_args)):
            #     max_arg = max_args[max_arg_ind]
            #     if flower_info[max_arg] > 0:
            #         chosen_flowers = []
            #         chosen_flowers.append(Flower(color=FlowerColors(max_arg[0]),
            #                                      type=FlowerTypes(max_arg[1]),
            #                                      size=FlowerSizes(max_arg[2])))
            #         chosen_flower_counts = dict(Counter(np.asarray(chosen_flowers)))
            #         chosen_bouquet = Bouquet(chosen_flower_counts)
            #         bouquet_for_all[sorted_max_args[max_arg_ind]][2] = chosen_bouquet

            return bouquet_for_all

            # # if nothing works, random
            # remaining_flowers = flower_counts.copy()
            # num_remaining = sum(remaining_flowers.values())
            # size = int(np.random.randint(0, min(MAX_BOUQUET_SIZE, num_remaining) + 1))
            # if size > 0:
            #     chosen_flowers = np.random.choice(flatten_counter(remaining_flowers), size=(size,), replace=False)
            #     chosen_flower_counts = dict(Counter(chosen_flowers))
            #     for k, v in chosen_flower_counts.items():
            #         remaining_flowers[k] -= v
            #         assert remaining_flowers[k] >= 0
            # else:
            #     chosen_flower_counts = dict()
            # chosen_bouquet = Bouquet(chosen_flower_counts)
            # return self.suitor_id, self.recipient_ids[0], chosen_bouquet

        else:  # training phase: conduct controlled experiments
            for ind in range(len(self.recipient_ids)):
                recipient_id = self.recipient_ids[ind]
                chosen_flowers = self._prepare_bouquet(flower_info, recipient_id)

                # build the bouquet
                chosen_flower_counts = dict(Counter(np.asarray(chosen_flowers)))
                chosen_bouquet = Bouquet(chosen_flower_counts)
                bouquet_for_all.append([self.suitor_id, recipient_id, chosen_bouquet])

                # store feedback values if available
                if len(self.feedback) > 0:
                    feedback_recipient_score = self.feedback[-1][recipient_id][1]
                    last_bouquet_recipient = self.last_bouquet[ind]
                    # TODO loop over all flowers in the bouquet; currently there's just one
                    c_ind = list(last_bouquet_recipient[2].colors.keys())[0].value
                    t_ind = list(last_bouquet_recipient[2].types.keys())[0].value
                    s_ind = list(last_bouquet_recipient[2].sizes.keys())[0].value
                    self.train_feedback[ind][c_ind][t_ind][s_ind] = feedback_recipient_score

            # update last_bouquet
            self.last_bouquet = bouquet_for_all

            return bouquet_for_all

    def _prepare_bouquet(self, flower_info, recipient_id):
        chosen_flowers = []  # for building a bouquet later
        tested = False

        # color
        for c_test_ind in range(len(self.to_be_tested[str(recipient_id)][0])):
            c_test = self.to_be_tested[str(recipient_id)][0][c_test_ind]
            nonzero_items = np.nonzero(flower_info[c_test.value])
            if len(nonzero_items[0]) > 0:
                # decrement flower_info at c_test, t_test, s_test
                flower_info[c_test.value][nonzero_items[0][0]][nonzero_items[1][0]] -= 1
                # decrement c_test from self.to_be_tested
                self.to_be_tested[str(recipient_id)][0].remove(c_test)
                tested = True

                # TODO for now only append one flower but we'll consider bouquet size later
                # for (t, s) in zip(nonzero_items[0], nonzero_items[1]):
                chosen_flowers.append(Flower(color=c_test,
                                             type=FlowerTypes(nonzero_items[0][0]),
                                             size=FlowerSizes(nonzero_items[1][0])))
                break

        # type
        if not tested:
            for t_test_ind in range(len(self.to_be_tested[str(recipient_id)][1])):
                t_test = self.to_be_tested[str(recipient_id)][1][t_test_ind]
                nonzero_items = np.nonzero(flower_info[t_test.value])
                if len(nonzero_items[0]) > 0:
                    # decrement flower_info at c_test, t_test, s_test
                    flower_info[nonzero_items[0][0]][t_test.value][nonzero_items[1][0]] -= 1
                    # decrement t_test from self.to_be_tested
                    self.to_be_tested[str(recipient_id)][1].remove(t_test)
                    tested = True

                    # TODO for now only append one flower but we'll consider bouquet size later
                    # for (c, s) in zip(nonzero_items[0], nonzero_items[1]):
                    chosen_flowers.append(Flower(color=FlowerColors(nonzero_items[0][0]),
                                                 type=t_test.value,
                                                 size=FlowerSizes(nonzero_items[1][0])))
                    break

        # size
        if not tested:
            for s_test_ind in range(len(self.to_be_tested[str(recipient_id)][2])):
                s_test = self.to_be_tested[str(recipient_id)][2][s_test_ind]
                nonzero_items = np.nonzero(flower_info[s_test.value])
                if len(nonzero_items[0]) > 0:
                    # decrement flower_info at c_test, t_test, s_test
                    flower_info[nonzero_items[0][0]][nonzero_items[1][0]][s_test.value] -= 1
                    # decrement s_test from self.to_be_tested
                    self.to_be_tested[str(recipient_id)][2].remove(s_test)

                    # TODO for now only append one flower but we'll consider bouquet size later
                    # for (c, s) in zip(nonzero_items[0], nonzero_items[1]):
                    chosen_flowers.append(Flower(color=FlowerColors(nonzero_items[0][0]),
                                                 type=FlowerTypes(nonzero_items[1][0]),
                                                 size=s_test.value))
        return chosen_flowers

    @staticmethod
    def _flatten_flower_info(flower_counts):
        flowers = flower_counts.keys()
        flower_info = np.zeros((6, 4, 3))  # (color, type, size)
        for flower in flowers:
            flower_info[flower.color.value][flower.type.value][flower.size.value] = flower_counts[flower]
        return flower_info

    def zero_score_bouquet(self):
        """
        :return: a Bouquet for which your scoring function will return 0
        """
        # is there a guaranteed min?
        # i think the min is when we pick one attribute with 12 flowers, which is minimal in the best_arrangement vector
        # someone check that logic but I think it works?
        worstFlower = Flower(
            size = self.get_min_vector_attribute(self.best_arrangement_size_vec, FlowerSizes),
            color = self.get_min_vector_attribute(self.best_arrangement_color_vec, FlowerColors),
            type=self.get_min_vector_attribute(self.best_arrangement_type_vec, FlowerTypes)
        )
        return Bouquet({worstFlower: 12})

    def get_min_vector_attribute(self, vector, enumType):
        zipped = list(zip(vector, enumType))
        return min(zipped)[1]

    def one_score_bouquet(self):
        """
        :return: a Bouquet for which your scoring function will return 1
        """
        # the below is still true
        return self.best_arrangement

    def score_types(self, types: Dict[FlowerTypes, int]):
        """
        :param types: dictionary of flower types and their associated counts in the bouquet
        :return: A score representing preference of the flower types in the bouquet
        """
        # each vector is like [FlowerType.1 Count, FlowerType.2 Count]
        vector = [0] * len(FlowerTypes)

        for key, value in types.items():
            vector[key.value] = value

        return self.compute_distance_heuristic(vector, self.best_arrangement_type_vec) * 1.0/3.0

    def score_colors(self, colors: Dict[FlowerColors, int]):
        """
        :param colors: dictionary of flower colors and their associated counts in the bouquet
        :return: A score representing preference of the flower colors in the bouquet
        """
        vector = [0] * len(FlowerColors)

        for key, value in colors.items():
            vector[key.value] = value

        return self.compute_distance_heuristic(vector, self.best_arrangement_color_vec) * 1.0/3.0

    def score_sizes(self, sizes: Dict[FlowerSizes, int]):
        """
        :param sizes: dictionary of flower sizes and their associated counts in the bouquet
        :return: A score representing preference of the flower sizes in the bouquet
        """
        vector = [0] * len(FlowerSizes)

        for key, value in sizes.items():
            vector[key.value] = value

        return self.compute_distance_heuristic(vector, self.best_arrangement_size_vec) * 1.0/3.0

    def receive_feedback(self, feedback):
        """
        :param feedback:
        :return: nothing
        """
        self.feedback.append(feedback)
