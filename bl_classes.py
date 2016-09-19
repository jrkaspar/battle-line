"""Low-level classes for tracking state of a Battle Line round.

Intended to be imported by a higher-level game manager (play_bl).  The meat of
this file is the Round class, which stores all of the game info, along with
the nested Hand class, which stores player-specific info.
"""

import random, sys

N_FLAGS          = 9
STANDARD_WIN     = 5
BREAKTHROUGH_WIN = 3
FORMATION_SIZE   = 3
TROOP_SUITS      = 'roygbp'
TROOP_CONTENTS   = '0123456789' # 0 is lowest.
TACTICS          = {'Al':'Alexander',
                    'CC':'Companion Cavalry',
                    'Da':'Darius',
                    'De':'Deserter',
                    'Fo':'Fog',
                    'Mu':'Mud',
                    'Re':'Redeploy',
                    'Sc':'Scout',
                    'SB':'Shield Bearers',
                    'Tr':'Traitor'}
HAND_SIZE        = 7
POKER_HIERARCHY  = ('straight flush', 'triple', 'flush', 'straight', 'sum')
EPSILON          = 0.1 # Arbitrary number on (0,1) to break formation ties

class Player(object):
    """AIPlayer class that should be inherited from when making"""
    def __init__(self):
        super(AIPlayer, self).__init__()

    @classmethod
    def get_name(cls):
        """Name to use when presenting this class to the user"""
        raise Exception('Override the function "get_name" in your class')

    def play(self, r):
        """Must be overridden to perform a play"""
        raise Exception("AIPlayer must override this method")


class Round(object):
    """Store round info and interact with AI players.

    The only method that interacts with AIs is 'get_play'.

    gameType (str): How to treat rainbows ('rainbow', 'purple', 'vanlla').
    suits (str): Which suits are included for this game type.
    nPlayers (int)
    """

    def __init__(self, players, names, verbosity):
        """Instantiate a Round and its Hand sub-objects."""
        self.nPlayers = len(names)
        self.h = (self.Hand(i, names[i]) for i in range(self.nPlayers))

        initialBest = self.detect_formation(
                [v+TROOP_SUITS[0] for v in TROOP_CONTENTS[-3:]]) # Red 7, 8, 9
        self.flags = ({'played':{[], []},
                       'best':(initialBest, initialBest),
                       'fog':False,
                       'mud':False,
                       'winner':None}
                      for _ in range(N_FLAGS))
        self.best = initialBest

        self.whoseTurn = 0

        self.verbosity = verbosity
        self.zazz = ['[HANDS]', '[PLAYS]']

    def generate_decks_and_deal_hands(self):
        """Construct decks, shuffle, and deal."""
        troopDeck = []
        for suit in TROOP_SUITS:
            for number in TROOP_CONTENTS:
                troopDeck.append(number + suit)
        tacticsDeck = [key for key in TACTICS]

        # Start tracking unplayed cards.
        self.cardsLeft = {'troop':troopDeck[:], 'tactics':tacticsDeck[:]}

        random.shuffle(troopDeck)
        random.shuffle(tacticsDeck)
        self.decks = {'troop':troopDeck, 'tactics':tacticsDeck}

        for hand in self.h:
            for i in range(HAND_SIZE):
                hand.add(self.draw('troop'))
            if self.verbosity == 'verbose':
                hand.show(self.zazz[0])
                self.zazz[0] = ' ' * len(self.zazz[0])

    def draw(self, deckName):
        """Remove and return the top card of the deck."""
        return self.decks[deckName].pop()

    # Discard card from hand, then attempt to draw a new card.
    def replace_card(self, card, hand, deckName):
        """Drop the card and draw a new one."""
        if self.decks[deckName] != []:
            hand.add(self.draw(deckName))
            return True
        return False # Deck is empty.

    def get_play(self, p):
        """Retrieve and execute AI p's play for whoever's turn it is."""
        card, target, deckName = p.play(self)
        me = self.whoseTurn
        hand = self.h[me]

        if card in TACTICS:
            pass

        else: # Troop
            self.replace_card(card, hand, deckName)

            flag = self.flags[target]
            formationSize = FORMATION_SIZE
            if flag['mud']:
                formationSize += 1

            if len(flag[me]) < formationSize: # Legal play
                flag[me].append(card)

        if self.verbosity == 'verbose':
            print(self.zazz[1] + ' {} [{}] {}s {}'\
                    .format(hand.name, 'derp', 'derp', 'derp'))
            self.zazz[1] = ' ' * len(self.zazz[1])

    def check_formation_components(self, cards, formationSize=3):
        straight, triple, flush = False, False, False

        l = len(cards)
        if l > 1:
            values, suits = [c[0] for c in cards], [c[1] for c in cards]
            values.sort()

            spacing = [int(values[i+1]) - int(values[i]) for i in range(l-1)]
            if sum(spacing) <= formationSize - 1:
                straight = True
            elif spacing.count(0) == l-1:
                triple = True

            if suits.count(suits[0]) == l:
                flush = True

            return straight, triple, flush

        else: # All formations are still possible with one or no cards played.
            return True, True, True

    def detect_formation(self, cards): # Assume wilds pre-specified
        l = len(cards)
        assert 3 <= l <= 4 # Allow for Mud.

        straight, triple, flush = self.check_formation_components(cards)

        if straight and flush:
            fType = 'straight flush'
        elif triple:
            fType = 'triple'
        elif flush:
            fType = 'flush'
        elif straight:
            fType = 'straight'
        else:
            fType = 'sum'

        return {'cards':cards,
                'formation':fType,
                'strength':sum([int(c[0]) for c in cards])}

    def possible_straights(self, cards, formationSize=3):
        """Return a seq of conceivable straight continuations."""
        minVal, maxVal = int(TROOP_CONTENTS[0]), int(TROOP_CONTENTS[-1])
        allStraights = [range(i, i + formationSize)
                        for i in range(minVal, maxVal - formationSize + 2)]

        cardValues = [int(card[0]) for card in cards]

        out = []
        for straight in allStraights:
            for value in cardValues:
                if value not in straight:
                    break
            else:
                possibleStraight = list(straight)
                for value in cardValues: # Skip cards already in hand.
                    possibleStraight.remove(value)
                out.append(list(map(str, possibleStraight)))

        return list(reversed(out)) # Strongest first

    def still_available(self, card):
        """Return whether a card might still be available to draw and play."""
        return True
    
    def best_case(self, cards, formationSize=3):
        """Return the best possible continuation of a formation."""
        # Ignore tactics for now.

        if cards == []:
            return self.best

        straight, triple, flush = self.check_formation_components(cards)

        if straight:
            possibleStraights = self.possible_straights(cards, formationSize)
            print(possibleStraights)

        if straight and flush:
            suit = cards[0][1]
            for straight in possibleStraights:
                for value in straight:
                    card = value + suit
                    if card not in self.cardsLeft['troop']:
                        break
                else:
                    return self.detect_formation(cards +\
                             [value + suit for value in straight])

        elif triple:
            for value in values:
                count = 0
                for card in cards + self.cardsLeft['troop']:
                    if card[0] == value:
                        count += 1
                        if count == formationSize:
                            return {'type'     : 'triple',
                                    'strength' : int(value) * formationSize}

#        elif flush:
#            for suit in suits:
#                strengths = []
#                for value in TROOP_CONTENTS:
#                    if value + suit in cards or\
#                       value + suit in self.cardsLeft['troop']:
#                        strengths.append(int(value))
#                        if len(strengths) == formationSize:
#                            return {'type'     : 'flush',
#                                    'strength' : sum(strengths)}
#
#        elif straight:
#            for value in TROOP_CONTENTS:
#                numbersAvailable = (c[0] for c in cards +\
#                                                  self.cardsLeft['troop'])
#                v = int(value)
#                candidateFormation = range(v, v - formationSize, -1)
#                for candidate in candidateFormation:
#                    if c not in numbersAvailable:
#                        break
#                else:
#                    return {'type'     : 'straight',
#                            'strength' : sum(candidateFormation)}
#
#        else: # Sum
#            pass


    def compare_formations(self, formations):
        ranks = (POKER_HIERARCHY.index(f['type']) for f in formations)
        if ranks[0] != ranks[1]:
            return ranks.index(min(ranks))
        else: # Same formation type
            strengths = (f['strength'] for f in formations)
            if strengths[0] != strengths[1]:
                return strengths.index(max(strengths))
            else: # Identical formations
                # Tie breaks against current player, who finished later.
                return 1 - self.whoseTurn

    def check_flag(self, flag):
        if flag['winner'] == None:
            formationSize = FORMATION_SIZE
            if flag['mud']:
                formationSize += 1

            finishedPlayers = []
            for player in (0, 1):
                if len(flag[player]) == formationSize:
                    finishedPlayers.append(player)
            
            formations = (flag[0], flag[1])
            if len(finishedPlayers) == 2: # Both players ready 
                flag['winner'] = compare_formations(formations)
            elif len(finishedPlayers) == 1: # One attacker seeks a proof.
                for player in (0, 1):
                    if player not in finishedPlayers: # Defender
                        formations[player] = best_case(formations[player],
                                                       formationSize)
                        # Tie goes to attacker since he finished first.
                        formations[player]['strength'] -= EPSILON
                        if compare_formations(formations) == 1 - player:
                            flag['winner'] = 1 - player # Attacker wins.

    def get_scout_discard(self):
        pass


    class Hand(object):
        """Manage one player's hand of cards.

        cards (list of dict): One dict per card.  Keys:
          name (str): card name (e.g., '2?' is a rainbow two)
          time (int): turn number in which card was drawn
          direct (list of char): hint info that matches the card; can be either
            a color or a number; chronological; duplicates allowed
          indirect (list of char): same as direct but info does not match card
          known (bool): whether card can be deduced solely from public info
        seat (int): Player ID number (starting player is 0).
        """

        def __init__(self, seat, name):
            """Instantiate a Hand."""
            self.cards = []
            self.seat = seat
            self.name = name

        def show(self, zazz):
            """Print cards (verbose output only)."""
            print(zazz + ' ' + self.name + ': ' + ' '.join(self.cards))

        def add(self, newCard, turnNumber):
            """Add a card to the hand."""
            self.cards.append(newCard)

        def drop(self, card):
            """Discard a card from the hand."""
            self.cards.remove(card)
