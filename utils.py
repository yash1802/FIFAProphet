# coding: utf-8
"""
Functions that give the data in the files, sometimes raw, with some cleaning
and/or summarization.
"""
from random import random
import pandas as pd
import pygal
from sklearn.preprocessing import StandardScaler


RAW_MATCHES_FILE = 'raw_matches.csv'
RAW_WINNERS_FILE = 'raw_winners.csv'
TEAM_RENAMES_FILE = 'team_renames.csv'


def apply_renames(column):
    """Apply team renames to a team column from a dataframe."""
    with open(TEAM_RENAMES_FILE) as renames_file:
        renames = dict(l.strip().split(',')
                       for l in renames_file.readlines()
                       if l.strip())

        def renamer(team):
            return renames.get(team, team)

    return column.map(renamer)


def get_matches(with_team_stats=False, duplicate_with_reversed=False,
                exclude_ties=False):
    """Create a dataframe with matches info."""
    matches = pd.DataFrame.from_csv(RAW_MATCHES_FILE)
    for column in ('team1', 'team2'):
        matches[column] = apply_renames(matches[column])

    if duplicate_with_reversed:
        id_offset = len(matches)

        matches2 = matches.copy()
        matches2.rename(columns={'team1': 'team2',
                                 'team2': 'team1',
                                 'score1': 'score2',
                                 'score2': 'score1'},
                        inplace=True)
        matches2.index = matches2.index.map(lambda x: x + id_offset)

        matches = pd.concat((matches, matches2))

    def winner_from_score_diff(x):
        if x > 0:
            return 1
        elif x < 0:
            return 2
        else:
            return 0

    matches['score_diff'] = matches['score1'] - matches['score2']
    matches['winner'] = matches['score_diff']
    matches['winner'] = matches['winner'].map(winner_from_score_diff)

    if exclude_ties:
        matches = matches[matches['winner'] != 0]

    if with_team_stats:
        stats = get_team_stats()

        matches = matches.join(stats, on='team1')\
                         .join(stats, on='team2', rsuffix='_2')

    return matches


def get_winners():
    """Create a dataframe with podium positions info."""
    winners = pd.DataFrame.from_csv(RAW_WINNERS_FILE)
    winners.team = apply_renames(winners.team)

    return winners


def get_team_stats():
    """Create a dataframe with useful stats for each team."""
    winners = get_winners()
    matches = get_matches()

    teams = set(matches.team1.unique()).union(matches.team2.unique())

    stats = pd.DataFrame(list(teams), columns=['team'])

    stats = stats.set_index('team')

    for team in teams:
        team_matches = matches[(matches.team1 == team) |
                               (matches.team2 == team)]
        stats.loc[team, 'matches_played'] = len(team_matches)

        # wins where the team was on the left side (team1)
        wins1 = team_matches[(team_matches.team1 == team) &
                             (team_matches.score1 > team_matches.score2)]
        # wins where the team was on the right side (team2)
        wins2 = team_matches[(team_matches.team2 == team) &
                             (team_matches.score2 > team_matches.score1)]

        stats.loc[team, 'matches_won'] = len(wins1) + len(wins2)

        stats.loc[team, 'years_played'] = len(team_matches.year.unique())

        team_podiums = winners[winners.team == team]
        to_score = lambda position: 2 ** (5 - position)  # better position -> more score, exponential
        stats.loc[team, 'podium_score'] = team_podiums.position.map(to_score).sum()

        stats.loc[team, 'cups_won'] = len(team_podiums[team_podiums.position == 1])

    stats['matches_won_percent'] = stats['matches_won'] / stats['matches_played'] * 100.0
    stats['podium_score_yearly'] = stats['podium_score'] / stats['years_played']
    stats['cups_won_yearly'] = stats['cups_won'] / stats['years_played']

    return stats


def extract_samples(matches, origin_features, result_feature):
    inputs = [tuple(matches.loc[i, feature]
                    for feature in origin_features)
              for i in matches.index]

    outputs = tuple(matches[result_feature].values)

    assert len(inputs) == len(outputs)

    return inputs, outputs


def graph_xy(data, feature_x, feature_y, feature_group):
    groups = {}

    for index in data.index.values:
        group = data.loc[index, feature_group]
        x = data.loc[index, feature_x]
        y = data.loc[index, feature_y]

        if group not in groups:
            groups[group] = []
        groups[group].append((x, y))

    chart = pygal.XY(stroke=False,
                     title='Samples',
                     style=pygal.style.CleanStyle)

    for group, points in groups.items():
        chart.add(str(group), points)

    return chart


def normalize(array):
    scaler = StandardScaler()
    array = scaler.fit_transform(array)

    return scaler, array


def split_samples(inputs, outputs, percent=0.75):
    assert len(inputs) == len(outputs)

    inputs1 = []
    inputs2 = []
    outputs1 = []
    outputs2 = []

    for i, inputs_row in enumerate(inputs):
        if random() < percent:
            input_to = inputs1
            output_to = outputs1
        else:
            input_to = inputs2
            output_to = outputs2

        input_to.append(inputs_row)
        output_to.append(outputs[i])

    return inputs1, outputs1, inputs2, outputs2


def graph_matches_results_scatter(matches, feature_x, feature_y):
    wins1 = matches[matches.score1 > matches.score2]
    wins2 = matches[matches.score1 < matches.score2]
    ties = matches[matches.score1 == matches.score2]

    graph = pygal.XY(stroke=False,
                     title='Results dispersion by %s, %s' % (feature_x, feature_y),
                     x_title=feature_x,
                     y_title=feature_y,
                     print_values=False)
    graph.add('wins 1', zip(wins1[feature_x], wins1[feature_y]))
    graph.add('wins 2', zip(wins2[feature_x], wins2[feature_y]))
    graph.add('ties', zip(ties[feature_x], ties[feature_y]))

    return graph


def graph_teams_stat_bars(team_stats, stat):
    sorted_team_stats = team_stats.sort(stat)
    graph = pygal.Bar(show_legend=False,
                      title='Teams by ' + stat,
                      x_title='team',
                      y_title=stat,
                      print_values=False)
    graph.x_labels = list(sorted_team_stats.index)
    graph.add(stat, sorted_team_stats[stat])

    return graph
