import operator
import threading
import time

from .processing import wrap_env
from . import tetris_util as utils

import gym_tetris
import numpy as np
import random
import matplotlib.pyplot as plt
from nes_py.wrappers import JoypadSpace
from gym_tetris.actions import SIMPLE_MOVEMENT


class GeneticAgent:
    """
    One agent/player with it's own set of
    weights that affect how it plays.
    """

    def __init__(self, hole_weight=random.uniform(-1, 1),
                 clear_weight=random.uniform(-1, 1), bump_weight=random.uniform(-1, 1)):
        self.hole_weight = hole_weight
        self.clear_weight = clear_weight
        self.bump_weight = bump_weight

        self.tot_score = 0

    def random(self):
        self.hole_weight = random.uniform(-1, 1)
        self.clear_weight = random.uniform(-1, 1)
        self.bump_weight = random.uniform(-1, 1)

    def best_move(self, state, current_piece):
        """
        Uses heuristics to figure out which move is the best one for the given
        piece in the given state. Iterates over all possible moves and calculates
        the heuristic score of the board if that move is made, and returns the
        actions needed for the best obtainable state.
        """
        global test_state
        rots, shape = utils.get_rotations(current_piece)
        if rots is None:
            return [[0]]
        best_rotation, best_x_offset, y_steps_best, best_score = None, None, None, None

        for rot in range(rots):
            current_shape = np.rot90(shape, - rot)
            for x in range(len(state[0][0]) - len(current_shape[0]) + 1):
                y, new_state = utils.y_collision_state(state[0], current_piece, current_shape, x)
                # y, new_state = utils.y_collision_state(use_state, current_shape, x)
                # print(current_shape)
                # print("x_off =", x, "collision after", y, "\n")  # Debugging

                score = self._calc_score(new_state, current_piece)
                # time.sleep(2)
                if best_score is None or score > best_score:
                    best_rotation = rot
                    best_x_offset = x
                    y_steps_best = max(y - 3, 0)
                    best_score = score

        # TODO optimize actions
        actions = [[1] * best_rotation,
                   [4] * 11,  # Very primitive solution, should be optimized
                   [3] * best_x_offset,
                   [5] * y_steps_best,
                   [0] * 3]
        return actions

    def get_weights(self):
        return self.hole_weight, self.clear_weight, self.bump_weight

    def _calc_score(self, new_state, current_piece):
        holes, clears, bumpiness = utils.get_heuristics(new_state, current_piece)
        return self.clear_weight * clears - self.hole_weight * holes - self.bump_weight * bumpiness


class GenePool:
    """
    The genetic algorithm, based on survival of the fittest.
    Creates a number of players (GeneticAgents) with separate random weights.
    Then iterates over each one, letting them play a given number of games, each with
    a given number of max moves. After each player has finished their games, evolution
    will take place. The best some percentage of players are kept and transferred to the
    next generation. To fill up the population once gain, the transferred players are
    'crossbred' so that their weights are passed on to the new players.
    There is also a certain chance that a mutation will take place, meaning that a new player
    gets a random weight, instead of one inherited from the preivous generation.
    """

    def __init__(self, cores=4, population=12, mutateChance=0.05, games=5, moves=150, replacePercent=0.7, debug=False):
        self.population = population
        self.mutateChance = mutateChance
        self.maxGames = games
        self.maxMoves = moves
        self.replacePercent = replacePercent
        self.debug = debug
        self.sem = threading.Semaphore(cores)  # https://github.com/JLMadsen/TetrisAI

    def train(self, generations):
        players = []

        for _ in range(self.population):
            players.append(self._random_agent())

        print("Training Generation #0")
        players = self._train_generation(players)

        average_scores = [sum([player.tot_score for player in players]) / len(players)]
        average_weights = [(sum([player.hole_weight for player in players]) / len(players),
                            sum([player.clear_weight for player in players]) / len(players),
                            sum([player.bump_weight for player in players]) / len(players))]

        print(f"Initial avg line: {average_scores[0]} | min({players[0].tot_score}) | max ({players[-1].tot_score})"
              f"\nWeights:{average_weights[0]}.")

        for i_gen in range(1, generations + 1):
            print("\nTraining Generation #{}".format(i_gen))
            new_players = players = players[
                                    int(len(players) * self.replacePercent):]  # keep the best replacePercent players

            if self.debug:
                print(f"DEBUG: Last generations best had: {new_players[0].tot_score} and {new_players[-1].tot_score}")

            while len(new_players) < self.population:
                new_players.append(self._cross_over(*random.sample(players, 2)))

            if self.debug:
                print(f'DEBUG: {len(new_players)}')

            new_players = self._train_generation(new_players)

            gen_avg_score = sum([player.tot_score for player in new_players]) / len(new_players)
            gen_avg_weights = (sum([player.hole_weight for player in new_players]) / len(new_players),
                               sum([player.clear_weight for player in new_players]) / len(new_players),
                               sum([player.bump_weight for player in new_players]) / len(new_players))
            average_scores.append(gen_avg_score)
            average_weights.append(gen_avg_weights)

            players = new_players

            print("Generation {gen: <2} ended with an average of {avg_score: <5} lines cleared."
                  "MIN|MAX: {min: <5} | {max: <5}\nWeight averages are: {weights}".format(gen=i_gen,
                                                                                          avg_score=gen_avg_score,
                                                                                          min=players[0].tot_score,
                                                                                          max=players[-1].tot_score,
                                                                                          weights=gen_avg_weights))
            plt.plot(average_scores)
            plt.xlabel("Generation")
            plt.ylabel("Lines cleared")
            plt.title("Average score per generation")
            plt.show()

        if self.debug:
            print("DEBUG: Finalist players:")
            for player in players:
                print(player.tot_score, ":", player.get_weights())

        return players[-1]

    def _train_individual(self, player: GeneticAgent):
        self.sem.acquire()
        try:
            env = gym_tetris.make('TetrisA-v1')
            env = JoypadSpace(env, SIMPLE_MOVEMENT)
            env = wrap_env(env, buffersize=1)

            totalscore = 0
            for _ in range(self.maxGames):
                _ = env.reset()
                state, reward, done, info = env.step(0)
                score = 0

                moves = 0
                while not done and moves < self.maxMoves:
                    # Very primitive way of checking if a piece was placed, replace if possible
                    # Tends to fail in high builds and in higher levels of the game
                    if state[0][0][5] != 0:
                        actions = player.best_move(state, info['current_piece'])
                        moves += 1

                        for sub_arr in actions:
                            for action in sub_arr:
                                # primitive way of preventing the env from crashing due to stepping while done
                                if done:
                                    break
                                state, reward, done, info = env.step(action)
                                score += reward

                                if done:
                                    break
                                    # Buffers an extra action to hinder lossy inputs
                                state, reward, done, info = env.step(0)
                                score += reward
                    else:
                        state, reward, done, info = env.step(5)
                        score += reward
                totalscore += score
            player.tot_score = totalscore
            env.close()
        finally:
            self.sem.release()

    def _train_generation(self, players):
        threads = []
        for player in players:
            thread = threading.Thread(target=self._train_individual, args=(player,))
            threads.append(thread)
            thread.start()

        print("Progress: ", sep=' ', end='', flush=True)
        for thread in threads:
            thread.join()
            print("|", sep=' ', end='', flush=True)

        print("\n")

        return sorted(players, key=operator.attrgetter('highscore'))

    def _cross_over(self, parent: GeneticAgent, parent2: GeneticAgent):
        child = GeneticAgent()
        child.clear_weight = parent2.clear_weight if random.getrandbits(1) == 0 else parent.clear_weight
        child.hole_weight = parent2.hole_weight if random.getrandbits(1) == 0 else parent.hole_weight
        child.bump_weight = parent2.bump_weight if random.getrandbits(1) == 0 else parent.bump_weight

        if random.random() < self.mutateChance:
            child.clear_weight = random.uniform(-1, 1)
        if random.random() < self.mutateChance:
            child.hole_weight = random.uniform(-1, 1)
        if random.random() < self.mutateChance:
            child.bump_weight = random.uniform(-1, 1)

        return child

    def _random_agent(self) -> GeneticAgent:
        return GeneticAgent(random.random(), random.random(), random.random())


test_state = np.array([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
                       [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
                       [0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
                       [0, 0, 0, 0, 0, 1, 0, 0, 1, 1],
                       [1, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                       [0, 1, 1, 1, 1, 1, 0, 1, 1, 0],
                       [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
                       ])

if __name__ == "__main__":
    print("")
