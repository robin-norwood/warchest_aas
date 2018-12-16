from warchest.errors import APIError
from warchest.models import units
from warchest.utils import list_get
from warchest.models.board import LETTER_LIST, POSITIONS_LIST, CONTROL_POINTS

PASS = 'pass'
INITIATIVE = 'initiative'
RECRUIT = 'recruit'
DEPLOY = 'deploy'
BOLSTER = 'bolster'
MOVE = 'move'
CONTROL = 'control'


def get_possible(game, coin):
    game.is_it_my_turn()
    zones = game.zones[game.active_player]

    if coin == 'no-op' and len(zones['hand'].coins) == 0: 
        return {
            PASS: True
        }

    if coin not in zones['hand']['coins']:

        raise APIError("Can't do hypothecticals with {} ({})".format(coin, zones['hand']['coins']), 410)

    actions = _get_facedown_actions(game, zones)
    actions.update(_get_deployment_actions(game, coin))
    actions.update(_get_activation_actions(game, coin))
    return actions


def _get_activation_actions(game, coin):
    return {
        MOVE: _get_moves(game, coin),
        'attack': False,
        'tactic': False,
        CONTROL: _get_control(game, coin)
    }

def _get_control(game, coin):
    coins = game.board.get_coins_spaces(coin)
    if len(coins) == 0:
        return False

    controls = []
    for name, pos in coins.items():
        if pos in CONTROL_POINTS:
            controls.append(name)

    return controls or False


def _get_moves(game, coin):
    coins = game.board.get_coins_spaces(coin)
    if len(coins) == 0:
        return False

    movement = {}

    for name, pos in coins.items():
        y = LETTER_LIST.index(pos[0])  # Letter
        x = int(pos[1])  # Number

        # Each coin has up to 6 possible movement spaces
        possible_spaces = [
            (x - 1, y - 1),
            (x - 1, y + 1),
            (x + 1, y - 1),
            (x + 1, y + 1),
            (x, y - 2),
            (x, y + 2)
        ]

        options = []
        # for each possible space, check to see if its on the board and empty
        for x, y in possible_spaces:
            letter = list_get(LETTER_LIST, y)

            if letter and x in POSITIONS_LIST[y]:
                valid_pos = "{}{}".format(letter, x)
                if valid_pos not in game.board.coins_on.keys():
                    options.append(valid_pos)
        if len(options) > 0:
            movement[name] = options

    if len(movement.keys()) > 0:
        return movement

    return False

def _get_deployment_actions(game, coin):
    bolster = False
    deploy = False

    if coin == units.ROYAL_TOKEN:
        return {
            DEPLOY: False,
            BOLSTER: False
        }
    # Is the unit on the board?
    spaces = game.board.get_coins_spaces(coin)
    if len(spaces) > 0:
        bolster = list(spaces.values())

    if len(spaces) == 0 or (len(spaces) == 1 and coin == units.FOOTMAN):
        deploy = [cp for cp in game.board[game.active_player] if cp not in list(game.board.coins_on.keys())]
        # UNIT: SCOUT
        if len(deploy) == 0:
            deploy = False

    return {
        DEPLOY: deploy,
        BOLSTER: bolster
    }


def _get_facedown_actions(game, zones):
    initiative = False
    recruit = False

    if len(zones['recruit'].coins) > 0:
        recruit = list(set(zones['recruit'].coins))  # TODO: What can I recruit

    if game.initiative != game.active_player and not game.initiative_taken_this_round:
        initiative = True

    return {
        PASS: True,  # You can always pass
        INITIATIVE: initiative,
        RECRUIT: recruit,
    }


def execute(game, coin, action, data=None):
    game.is_it_my_turn()
    possibles = get_possible(game, coin)
    zones = game.zones[game.active_player]
    if action not in possibles:
        raise APIError("Not a valid action", 400)

    if action == PASS:
        if len(zones['hand'].coins) > 0:
            zones['hand'].move(zones['facedown'], coin=coin)

    if action == INITIATIVE:
        if not possibles[INITIATIVE]:
            raise APIError("You already have initiative. Why don't you just pass?", 400)

        if game.initiative_taken_this_round:
            raise APIError("Your opponent just took initiative. Give him a moment in the sun", 400)

        game.take_initiative()
        zones['hand'].move(zones['facedown'], coin=coin)

    if action == RECRUIT:
        if not possibles[RECRUIT] or data not in possibles[RECRUIT]:
            raise APIError("Can't recruit that", 400)

        zones['hand'].move(zones['facedown'], coin=coin)
        zones['recruit'].move(zones['faceup'], coin=data)

    if action == DEPLOY:
        if not possibles[DEPLOY] or data not in possibles[DEPLOY]:
            raise APIError("Can't deploy there", 400)

        game.board.deploy(coin, data)
        zones['hand'].remove(coin=coin)

    if action == BOLSTER:
        if not possibles[BOLSTER] or data not in possibles[BOLSTER]:
            raise APIError("Can't bolster there", 400)

        game.board.bolster(coin, data)
        zones['hand'].remove(coin=coin)

    if action == MOVE:
        piece = list(data.keys())[0]
        to = data[piece]
        if not possibles[MOVE] or piece not in possibles[MOVE] or to not in possibles[MOVE][piece]:
            raise APIError("Can't move like that", 400)

        game.board.move(piece, to)
        zones['hand'].remove(coin=coin)

    if action == CONTROL:

        if not possibles[CONTROL] or data not in possibles[CONTROL]:
            raise APIError("Don't be so controlling", 400)

        game.board.control(data)
        zones['hand'].remove(coin=coin)

    game.set_zones(zones)
    game.your_turn()
    game.save()
