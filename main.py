#TODO: multiplayer
#TODO: save/load
# TODO: character creation
# TODO: main menu

from datetime import datetime
import json
import math
from conf import conf
from PyQt5 import QtCore, QtGui, QtWidgets
import sys
from components import ProgressBar, TableBox, ListBox
from utils import toRoman, toArabic

K = conf.K
randseed = conf.randseed
template = conf.template
Random = conf.Random
Pick = conf.Pick
LevelUpTime = conf.LevelUpTime
GenerateName = conf.GenerateName

game = {}
lasttick = timerid = None

ExpBar = PlotBar = TaskBar = QuestBar = EncumBar = None
Traits = Stats = Spells = Equips = Inventory = Plots = Quests = None
Kill = None
AllBars = AllLists = None
dealing = False

def Odds(chance, outof):
    return Random(outof) < chance


def RandSign():
    return Random(2) * 2 - 1


def TaskDone():
    return TaskBar.done()


def RandomLow(below):
    return min([Random(below), Random(below)])


def PickLow(s):
    return s[RandomLow(s.length)]


def Copy(s, b, l):
    return s[b - 1:l]


def Ends(s, e):
    return Copy(s, 1 + len(s) - len(e), len(e)) == e


def Plural(s):
    if Ends(s, "y"):
        return Copy(s, 1, s.length - 1) + "ies"
    elif Ends(s, "us"):
        return Copy(s, 1, s.length - 2) + "i"
    elif Ends(s, "ch") or Ends(s, "x") or Ends(s, "s") or Ends(s, "sh"):
        return s + "es"
    elif Ends(s, "f"):
        return Copy(s, 1, s.length - 1) + "ves"
    elif Ends(s, "man") or Ends(s, "Man"):
        return Copy(s, 1, s.length - 2) + "en"
    else:
        return s + "s"


def Split(s, field, separator=None):
    return s.split(separator or "|")[field]


def Indefinite(s, qty):
    if qty == 1:
        if Pos(s[0], "AEIOU�aeiou�") > 0:
            return "an " + s
        else:
            return "a " + s
    else:
        return str(qty) + " " + Plural(s)


def Definite(s, qty):
    if qty > 1:
        s = Plural(s)
    return "the " + s


def prefix(a, m, s, sep=" "):
    m = abs(m)
    if (m < 1 or m > len(a)):
        return s
    return a[m - 1] + sep + s


def Sick(m, s):
    m = 6 - abs(m)
    return prefix(
        ["dead", "comatose", "crippled", "sick", "undernourished"],
        m,
        s
    )


def Young(m, s):
    m = 6 - abs(m)
    return prefix(
        ["foetal", "baby", "preadolescent", "teenage", "underage"],
        m,
        s
    )


def Big(m, s):
    return prefix(["greater", "massive", "enormous", "giant", "titanic"], m, s)


def Special(m, s):
    if Pos(" ", s) > 0:
        return prefix(["veteran", "cursed", "warrior", "undead", "demon"], m, s)
    else:
        return prefix(
            ["Battle-", "cursed ", "Were-", "undead ", "demon "],
            m,
            s,
            ""
        )


def Dequeue():
    while (TaskDone()):
        if Split(game["task"], 0) == 'kill':
            if Split(game["task"], 3) == '*':
                WinItem()
            elif Split(game["task"], 3):
                Add(Inventory, (
                    Split(game["task"], 1) + ' ' + Split(game["task"], 3)).lower() , 1)
        elif game["task"] == 'buying':
            Add(Inventory, 'Gold', -EquipPrice())
            WinEquip()
        elif (game["task"] == 'market') or (game["task"] == 'sell'):
            if game["task"] == 'sell':
                amt = GetI(Inventory, 1) * GetI(Traits, 'Level')
                if Pos(' of ', Inventory.label(1)) > 0:
                    amt *= (1+RandomLow(10)) * \
                        (1+RandomLow(GetI(Traits, 'Level')))
                Inventory.remove1()
                Add(Inventory, 'Gold', amt)

            if Inventory.length() > 1:
                Inventory.scrollToTop()
                Task('Selling ' + Indefinite(Inventory.label(1), GetI(Inventory, 1)),
                     1 * 1000)
                game["task"] = 'sell'
                break

        old = game["task"]
        game["task"] = ''
        if len(game["queue"]) > 0:
            a = Split(game["queue"][0], 0)
            n = int(Split(game["queue"][0], 1))
            s = Split(game["queue"][0], 2)
            if a == 'task' or a == 'plot':
                game["queue"].pop(0)
                if a == 'plot':
                    CompleteAct()
                    s = 'Loading ' + game["bestplot"]
                Task(s, n * 1000)
            else:
                raise 'bah!' + a

        elif (EncumBar.done()):
            Task('Heading to market to sell loot', 4 * 1000)
            game["task"] = 'market'
        elif (Pos('kill|', old) <= 0) and (old != 'heading'):
            if GetI(Inventory, 'Gold') > EquipPrice():
                Task('Negotiating purchase of better equipment', 5 * 1000)
                game["task"] = 'buying'
            else:
                Task('Heading to the killing fields', 4 * 1000)
                game["task"] = 'heading'
        else:
            nn = GetI(Traits, 'Level')
            t = MonsterTask(nn)
            InventoryLabelAlsoGameStyleTag = 3
            nn = math.floor(
                (2 * InventoryLabelAlsoGameStyleTag * t['level'] * 1000) / nn)
            Task('Executing ' + t['description'], nn)


def Q(s):
    global game
    game['queue'].append(s)
    Dequeue()


def InterplotCinematic():
    r = Random(3)

    if r == 0:
        Q("task|1|Exhausted, you arrive at a friendly oasis in a hostile land")
        Q("task|2|You greet old friends and meet allies")
        Q("task|2|You are privy to a council of powerful do-gooders")
        Q("task|1|There is much to be done. You are chosen!")

    if r == 1:
        Q("task|1|Your quarry is in sight, but a mighty enemy bars your path!")
        nemesis = NamedMonster(GetI(Traits, "Level") + 3)
        Q("task|4|A desperate struggle commences with " + nemesis)

        s = Random(3)
        for i in range(1, Random(1 + game["act"] + 1) + 1):
            s += 1 + Random(2)

            if s % 3 == 0:
                Q("task|2|Locked in grim combat with " + nemesis)

            if s % 3 == 1:
                Q("task|2|" + nemesis + " seems to have the upper hand")

            if s % 3 == 2:
                Q("task|2|You seem to gain the advantage over " + nemesis)

        Q(
            "task|3|Victory! " +
            nemesis +
            " is slain! Exhausted, you lose conciousness"
        )
        Q("task|2|You awake in a friendly place, but the road awaits")

    if r == 2:
        nemesis2 = ImpressiveGuy()
        Q(
            "task|2|Oh sweet relief! You've reached the protection of the good " +
            nemesis2
        )
        Q(
            "task|3|There is rejoicing, and an unnerving encouter with " +
            nemesis2 +
            " in private"
        )
        Q("task|2|You forget your " + BoringItem() + " and go back to get it")
        Q("task|2|What's self!? You overhear something shocking!")
        Q("task|2|Could " + nemesis2 + " be a dirty double-dealer?")
        Q(
            "task|3|Who can possibly be trusted with self news!? ... Oh yes, of course"
        )

    Q("plot|1|Loading")


def NamedMonster(level):
    lev = 0
    result = ""
    for i in range(5):
        m = Pick(K["Monsters"])
        if not result or abs(level - int(Split(m, 1))) < abs(level - lev):
            result = Split(m, 0)
            lev = int(Split(m, 1))

    return GenerateName() + " the " + result


def ImpressiveGuy():
    return (
        Pick(K["ImpressiveTitles"]) +
        (" of the " + Pick(K["Races"])
         if Random(2) else " of " + GenerateName())
    )


def MonsterTask(level):
    definite = False
    for i in range(level, 0, -1):
        if Odds(2, 5):
            level += RandSign()

    if level < 1:
        level = 1

    monster = lev = None
    if Odds(1, 25):
        monster = " " + Split(Pick(K["Races"]), 0)
        if Odds(1, 2):
            monster = "passing" + monster + " " + Split(Pick(K["Klasses"]), 0)
        else:
            monster = PickLow(K["Titles"]) + " " + \
                GenerateName() + " the" + monster
            definite = True
        lev = level
        monster = monster + "|" + str(level) + "|*"
    elif game["questmonster"] and Odds(1, 4):
        monster = K["Monsters"][game["questmonsterindex"]]
        lev = int(Split(monster, 1))
    else:
        monster = Pick(K["Monsters"])
        lev = int(Split(monster, 1))
        for ii in range(5):
            m1 = Pick(K["Monsters"])
            if abs(level - int(Split(m1, 1))) < abs(level - lev):
                monster = m1
                lev = int(Split(monster, 1))

    result = Split(monster, 0)
    game["task"] = "kill|" + monster

    qty = 1
    if level - lev > 10:
        qty = math.floor((level + Random(lev)) / max([lev, 1]))
        if qty < 1:
            qty = 1
        level = math.floor(level / qty)

    if level - lev <= -10:
        result = "imaginary " + result
    elif level - lev < -5:
        i = 10 + (level - lev)
        i = 5 - Random(i + 1)
        result = Sick(i, Young(lev - level - i, result))
    elif level - lev < 0 and Random(2) == 1:
        result = Sick(level - lev, result)
    elif level - lev < 0:
        result = Young(level - lev, result)
    elif level - lev >= 10:
        result = "messianic " + result
    elif level - lev > 5:
        i = 10 - (level - lev)
        i = 5 - Random(i + 1)
        result = Big(i, Special(level - lev - i, result))
    elif level - lev > 0 and Random(2) == 1:
        result = Big(level - lev, result)
    elif level - lev > 0:
        result = Special(level - lev, result)

    lev = level
    level = lev * qty

    if not definite:
        result = Indefinite(result, qty)
    return {"description": result, "level": level}


def EquipPrice():
    return (
        5 * GetI(Traits, "Level") * GetI(Traits, "Level") +
        10 * GetI(Traits, "Level") +
        20
    )


def Put(list, key, value):
    if type(key) is int:
        key = list.label(key)

    if list.fixedkeys:
        game[list.id][key] = value
    else:
        i = 0
        still = True
        for i in range(len(game[list.id])):
            if game[list.id][i][0] == key:
                game[list.id][i][1] = value
                still = False
                break
        if still and i == len(game[list.id]) - 1:
            game[list.id].append([key, value])

    list.PutUI(key, value)

    if key == "STR":
        EncumBar.reset(10 + value, EncumBar.Position())

    if (list == Inventory):
        cubits = 0
        for item in game["Inventory"][1:]:
            cubits += int(item[1])
        EncumBar.reposition(cubits)


def WinSpell():
    AddR(
        Spells,
        K["Spells"][
            RandomLow(
                min([GetI(Stats, "WIS") + GetI(Traits, "Level"), len(K["Spells"])])
            )
        ],
        1
    )


def LPick(list, goal):
    result = Pick(list)
    for i in range(1, 6):
        best = int(Split(result, 1))
        s = Pick(list)
        b1 = int(Split(s, 1))
        if abs(goal - best) > abs(goal - b1):
            result = s
    return result


def WinEquip():
    posn = Random(Equips.length())

    if not posn:
        stuff = K["Weapons"]
        better = K["OffenseAttrib"]
        worse = K["OffenseBad"]
    else:
        better = K["DefenseAttrib"]
        worse = K["DefenseBad"]
        stuff = K["Shields"] if posn == 1 else K["Armors"]

    name = LPick(stuff, GetI(Traits, "Level"))
    qual = int(Split(name, 1))
    name = Split(name, 0)
    plus = GetI(Traits, "Level") - qual
    if plus < 0:
        better = worse
    count = 0
    while count < 2 and plus:
        modifier = Pick(better)
        qual = int(Split(modifier, 1))
        modifier = Split(modifier, 0)
        if Pos(modifier, name) > 0:
            break
        if abs(plus) < abs(qual):
            break
        name = modifier + " " + name
        plus -= qual
        ++count

    if plus:
        name = str(plus) + " " + name
    if plus > 0:
        name = "+" + name

    Put(Equips, posn, name)
    game["bestequip"] = name
    if posn > 1:
        game["bestequip"] += " " + Equips.label(posn)


def WinStat():
    i = None
    if Odds(1, 2):
        i = Pick(K["Stats"])
    else:
        t = 0
        for key in K["Stats"]:
            s = GetI(Stats, key)
            t += s * s
        t = Random(t)
        for key in K["Stats"]:
            i = key
            s = GetI(Stats, key)
            t -= s * s
            if t < 0:
                return False
    Add(Stats, i, 1)


def SpecialItem():
    return InterestingItem() + " of " + Pick(K["ItemOfs"])


def InterestingItem():
    return Pick(K["ItemAttrib"]) + " " + Pick(K["Specials"])


def BoringItem():
    return Pick(K["BoringItems"])


def WinItem():
    Add(Inventory, SpecialItem(), 1)


def CompleteQuest():
    QuestBar.reset(50 + RandomLow(1000))
    if Quests.length:
        Quests.CheckAll()
        [WinSpell, WinEquip, WinStat, WinItem][Random(4)]()
    while Quests.length() > 99:
        Quests.remove0()

    game["questmonster"] = ""
    r = Random(5)

    if r == 0:
        level = GetI(Traits, "Level")
        lev = 0
        for i in range(1, 5):
            montag = Random(K["Monsters"].length)
            m = K["Monsters"][montag]
            l = int(Split(m, 1))
            if i == 1 or abs(l - level) < abs(lev - level):
                lev = l
                game["questmonster"] = m
                game["questmonsterindex"] = montag

        caption = "Exterminate " + Definite(Split(game["questmonster"], 0), 2)

    if r == 1:
        caption = "Seek " + Definite(InterestingItem(), 1)

    if r == 2:
        caption = "Deliver self " + BoringItem()

    if r == 3:
        caption = "Fetch me " + Indefinite(BoringItem(), 1)

    if r == 4:
        mlev = 0
        level = GetI(Traits, "Level")
        for ii in range(1, 3):
            montag = Random(K["Monsters"].length)
            m = K["Monsters"][montag]
            l = int(Split(m, 1))
            if ii == 1 or abs(l - level) < abs(mlev - level):
                mlev = l
                game["questmonster"] = m

        caption = "Placate " + Definite(Split(game["questmonster"], 0), 2)
        game["questmonster"] = ""

    if not game["Quests"]:
        game["Quests"] = []
    while len(game["Quests"]) > 99:
        game["Quests"].pop(0)
    game["Quests"].append(caption)
    game["bestquest"] = caption
    Quests.AddUI(caption)


def CompleteAct():
    Plots.CheckAll()
    game["act"] += 1
    PlotBar.reset(60 * 60 * (1 + 5 * game["act"]))
    game["bestplot"] = "Act " + toRoman(game["act"])
    Plots.AddUI(game["bestplot"])

    if game["act"] > 1:
        WinItem()
        WinEquip()


def Task(caption, msec):
    game["kill"] = caption + "..."
    if Kill:
        Kill.setText(game["kill"])
    TaskBar.reset(msec)


def Add(list, key, value=None):
    Put(list, key, value + GetI(list, key))

    if not value:
        return
    line = "Gained" if value > 0 else "Lost"
    if key == "Gold":
        key = "gold piece"
        line = "Got paid" if value > 0 else "Spent"
    if value < 0:
        value = -value
    line = line + " " + Indefinite(key, value)


def AddR(list, key, value):
    Put(list, key, toRoman(value + toArabic(Get(list, key))))


def Get(list, key):
    if list.fixedkeys:
        if type(key) is int:
            key = list.fixedkeys[key]
        return game[list.id][key]
    elif type(key) is int:
        if key < len(game[list.id]):
            return game[list.id][key][1]
        else:
            return ""
    else:
        for i in range(len(game[list.id])):
            if (game[list.id][i][0] == key):
                return game[list.id][i][1]
        return ""


def GetI(list, key):
    try: return int(Get(list, key))
    except: return 0


def LevelUp():
    Add(Traits, "Level", 1)
    Add(Stats, "HP Max", GetI(Stats, "CON") // 3 + 1 + Random(4))
    Add(Stats, "MP Max", GetI(Stats, "INT") // 3 + 1 + Random(4))
    WinStat()
    WinStat()
    WinSpell()
    ExpBar.reset(LevelUpTime(GetI(Traits, "Level")))


def ClearAllSelections():
    global AllLists
    for item in AllLists:
        item.ClearSelection()


def Pos(needle, haystack):
    return (haystack.index(needle) if needle in haystack else -1) + 1


def LoadGame(sheet):
    global game, AllBars, AllLists, Kill
    game = sheet

    randseed(game["seed"])
    [e.load(game) for e in (AllBars + AllLists)]

    if Kill:
        Kill.setText(game["kill"])
    ClearAllSelections()

    for i in [Plots, Quests]:
        i.CheckAll(True)

def Progress():
    global timerid, game, lasttick

    if TaskBar.done():
        game["tasks"] += 1
        game["elapsed"] += TaskBar.Max() // 1000

        ClearAllSelections()

        if game["kill"] == "Loading....":
            TaskBar.reset(0)

        gain = Pos("kill|", game["task"]) == 1
        if gain:
            if ExpBar.done():
                LevelUp()
            else:
                ExpBar.increment(TaskBar.Max() / 1000)

        if gain and game["act"] >= 1:
            if QuestBar.done() or not Quests.length:
                CompleteQuest()
            else:
                QuestBar.increment(TaskBar.Max() / 1000)

        if gain or not game["act"]:
            if PlotBar.done():
                InterplotCinematic()
            else:
                PlotBar.increment(TaskBar.Max() / 1000)

        Dequeue()
    else:
        elapsed = timeGetTime() - lasttick
        if (elapsed > 100):
            elapsed = 100
        if (elapsed < 0):
            elapsed = 0
        TaskBar.increment(elapsed)

    lasttick = timeGetTime()


def timeGetTime():
    return round(datetime.timestamp(datetime.now()) * 1000)


class Ui_progressQuest(object):
    def setupUi(self, progressQuest):
        global ExpBar, EncumBar, PlotBar, QuestBar, TaskBar, AllBars, AllLists
        global Traits, Stats, Spells, Equips, Inventory, Plots, Quests, Kill
        progressQuest.setObjectName("progressQuest")
        progressQuest.resize(1005, 596)
        self.gridLayout_3 = QtWidgets.QGridLayout(progressQuest)
        self.gridLayout_3.setSpacing(10)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.verticalLayout_14 = QtWidgets.QVBoxLayout()
        self.verticalLayout_14.setSizeConstraint(
            QtWidgets.QLayout.SetFixedSize)
        self.verticalLayout_14.setSpacing(0)
        self.verticalLayout_14.setObjectName("verticalLayout_14")
        self.label_10 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_10.setFont(font)
        self.label_10.setObjectName("label_10")
        self.verticalLayout_14.addWidget(self.label_10)

        self.characterSheetTable = Traits = TableBox("Traits", 2, K["Traits"])
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(100)
        sizePolicy.setVerticalStretch(0)
        self.characterSheetTable.setSizePolicy(sizePolicy)
        self.characterSheetTable.setMinimumSize(QtCore.QSize(240, 124))
        self.characterSheetTable.setMaximumSize(QtCore.QSize(240, 124))

        self.characterSheetTable.setObjectName("characterSheetTable")
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.characterSheetTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.characterSheetTable.setHorizontalHeaderItem(1, item)
        self.characterSheetTable.horizontalHeader().setDefaultSectionSize(60)
        self.characterSheetTable.horizontalHeader().setMinimumSectionSize(12)
        self.characterSheetTable.horizontalHeader().setStretchLastSection(True)
        self.characterSheetTable.verticalHeader().setStretchLastSection(False)

        self.verticalLayout_14.addWidget(self.characterSheetTable)
        self.characterStatsTable = Stats = TableBox("Stats", 2, K["Stats"])
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(100)
        sizePolicy.setHeightForWidth(
            self.characterStatsTable.sizePolicy().hasHeightForWidth())
        self.characterStatsTable.setSizePolicy(sizePolicy)
        self.characterStatsTable.setMaximumSize(QtCore.QSize(240, 188))
        self.characterStatsTable.setObjectName("characterStatsTable")
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.characterStatsTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.characterStatsTable.setHorizontalHeaderItem(1, item)
        self.characterStatsTable.horizontalHeader().setDefaultSectionSize(60)
        self.characterStatsTable.horizontalHeader().setMinimumSectionSize(12)
        self.characterStatsTable.horizontalHeader().setStretchLastSection(True)
        self.characterStatsTable.verticalHeader().setStretchLastSection(False)
        self.verticalLayout_14.addWidget(self.characterStatsTable)
        self.label_13 = QtWidgets.QLabel(progressQuest)
        self.label_13.setObjectName("label_13")
        self.verticalLayout_14.addWidget(self.label_13)
        self.experienceProgressBar = ExpBar = ProgressBar(
            "ExpBar", "$remaining XP needed for next level")
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.experienceProgressBar.sizePolicy().hasHeightForWidth())
        self.experienceProgressBar.setSizePolicy(sizePolicy)
        self.experienceProgressBar.setMaximumSize(QtCore.QSize(240, 16777215))
        self.experienceProgressBar.setObjectName("experienceProgressBar")
        self.verticalLayout_14.addWidget(self.experienceProgressBar)
        self.label_14 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_14.setFont(font)
        self.label_14.setObjectName("label_14")
        self.verticalLayout_14.addWidget(self.label_14)
        self.spellBookTable = Spells = TableBox("Spells", 2)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.spellBookTable.setSizePolicy(sizePolicy)
        self.spellBookTable.setMaximumSize(QtCore.QSize(240, 16777215))
        self.spellBookTable.setObjectName("spellBookTable")

        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.spellBookTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignJustify | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setPointSize(13)
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.spellBookTable.setHorizontalHeaderItem(1, item)
        self.spellBookTable.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        self.spellBookTable.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents)
        self.verticalLayout_14.addWidget(self.spellBookTable)
        self.gridLayout_3.addLayout(self.verticalLayout_14, 0, 0, 1, 1)
        self.verticalLayout_15 = QtWidgets.QVBoxLayout()
        self.verticalLayout_15.setSizeConstraint(
            QtWidgets.QLayout.SetMaximumSize)
        self.verticalLayout_15.setSpacing(0)
        self.verticalLayout_15.setObjectName("verticalLayout_15")
        self.label_11 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_11.setFont(font)
        self.label_11.setObjectName("label_11")
        self.verticalLayout_15.addWidget(self.label_11)
        self.equipmentTable = Equips = TableBox("Equips", 2, K["Equips"])
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(100)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.equipmentTable.sizePolicy().hasHeightForWidth())
        self.equipmentTable.setSizePolicy(sizePolicy)
        self.equipmentTable.setMinimumSize(QtCore.QSize(0, 224))
        self.equipmentTable.setMaximumSize(QtCore.QSize(16777215, 250))
        self.equipmentTable.setObjectName("equipmentTable")
        self.equipmentTable.horizontalHeader().setVisible(False)
        self.equipmentTable.horizontalHeader().setMinimumSectionSize(12)
        self.equipmentTable.horizontalHeader().setStretchLastSection(True)
        self.verticalLayout_15.addWidget(self.equipmentTable)
        self.label_15 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_15.setFont(font)
        self.label_15.setObjectName("label_15")
        self.verticalLayout_15.addWidget(self.label_15)
        self.inventoryTable = Inventory = TableBox("Inventory", 2)
        self.inventoryTable.setObjectName("inventoryTable")
        self.inventoryTable.setColumnCount(2)
        self.inventoryTable.setRowCount(0)
        self.inventoryTable.horizontalHeader().setVisible(False)
        self.inventoryTable.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        self.inventoryTable.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents)
        self.verticalLayout_15.addWidget(self.inventoryTable)
        self.label_16 = QtWidgets.QLabel(progressQuest)
        self.label_16.setObjectName("label_16")
        self.verticalLayout_15.addWidget(self.label_16)
        self.encumProgressBar = EncumBar = ProgressBar(
            "EncumBar", "$position/$max cubits")
        self.encumProgressBar.setObjectName("inventoryProgressBar")
        self.verticalLayout_15.addWidget(self.encumProgressBar)
        self.gridLayout_3.addLayout(self.verticalLayout_15, 0, 1, 1, 1)
        self.verticalLayout_16 = QtWidgets.QVBoxLayout()
        self.verticalLayout_16.setSizeConstraint(
            QtWidgets.QLayout.SetMinimumSize)
        self.verticalLayout_16.setSpacing(0)
        self.verticalLayout_16.setObjectName("verticalLayout_16")
        self.label_12 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_12.setFont(font)
        self.label_12.setObjectName("label_12")
        self.verticalLayout_16.addWidget(self.label_12)
        self.plotDevelopmentList = Plots = ListBox("Plots", 1)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(250)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.plotDevelopmentList.sizePolicy().hasHeightForWidth())
        self.plotDevelopmentList.setSizePolicy(sizePolicy)
        self.plotDevelopmentList.setObjectName("plotDevelopmentList")
        self.verticalLayout_16.addWidget(self.plotDevelopmentList)
        self.plotDevelopmentProgressBar = PlotBar = ProgressBar(
            "PlotBar", "$time remaining")
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.plotDevelopmentProgressBar.sizePolicy().hasHeightForWidth())
        self.plotDevelopmentProgressBar.setSizePolicy(sizePolicy)
        self.plotDevelopmentProgressBar.setMaximumSize(
            QtCore.QSize(250, 16777215))
        self.plotDevelopmentProgressBar.setObjectName(
            "plotDevelopmentProgressBar")
        self.verticalLayout_16.addWidget(self.plotDevelopmentProgressBar)
        self.label_17 = QtWidgets.QLabel(progressQuest)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_17.setFont(font)
        self.label_17.setObjectName("label_17")
        self.verticalLayout_16.addWidget(self.label_17)
        self.questList = Quests = ListBox("Quests", 1)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(250)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.questList.sizePolicy().hasHeightForWidth())
        self.questList.setSizePolicy(sizePolicy)
        self.questList.setObjectName("questList")
        self.verticalLayout_16.addWidget(self.questList)
        self.questProgressBar = QuestBar = ProgressBar(
            "QuestBar", "$percent% complete")
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.questProgressBar.sizePolicy().hasHeightForWidth())
        self.questProgressBar.setSizePolicy(sizePolicy)
        self.questProgressBar.setMaximumSize(QtCore.QSize(250, 16777215))
        self.questProgressBar.setObjectName("questProgressBar")
        self.verticalLayout_16.addWidget(self.questProgressBar)
        self.gridLayout_3.addLayout(self.verticalLayout_16, 0, 2, 1, 1)
        self.verticalLayout_17 = QtWidgets.QVBoxLayout()
        self.verticalLayout_17.setSpacing(0)
        self.verticalLayout_17.setObjectName("verticalLayout_17")
        self.mainLabel = Kill = QtWidgets.QLabel(progressQuest)
        self.mainLabel.setObjectName("mainLabel")
        self.verticalLayout_17.addWidget(self.mainLabel)
        self.taskProgressBar = TaskBar = ProgressBar("TaskBar", "$percent%")
        self.taskProgressBar.setObjectName("mainProgressBar")
        self.verticalLayout_17.addWidget(self.taskProgressBar)
        self.gridLayout_3.addLayout(self.verticalLayout_17, 1, 0, 1, 3)

        self.retranslateUi(progressQuest)
        QtCore.QMetaObject.connectSlotsByName(progressQuest)

    def retranslateUi(self, progressQuest):
        _translate = QtCore.QCoreApplication.translate
        progressQuest.setWindowTitle(
            _translate("progressQuest", "Progress Quest"))
        self.label_10.setText(_translate("progressQuest", "Character Sheet"))
        item = self.characterSheetTable.horizontalHeaderItem(0)
        item.setText(_translate("progressQuest", "Trait"))
        item = self.characterSheetTable.horizontalHeaderItem(1)
        item.setText(_translate("progressQuest", "Value"))
        __sortingEnabled = self.characterSheetTable.isSortingEnabled()
        self.characterSheetTable.setSortingEnabled(False)
        self.characterSheetTable.setSortingEnabled(__sortingEnabled)
        item = self.characterStatsTable.horizontalHeaderItem(0)
        item.setText(_translate("progressQuest", "Stat"))
        item = self.characterStatsTable.horizontalHeaderItem(1)
        item.setText(_translate("progressQuest", "Value"))
        __sortingEnabled = self.characterStatsTable.isSortingEnabled()
        self.characterStatsTable.setSortingEnabled(False)
        self.characterStatsTable.setSortingEnabled(__sortingEnabled)
        self.label_13.setText(_translate("progressQuest", "Experience"))
        self.label_14.setText(_translate("progressQuest", "Spell Book"))
        item = self.spellBookTable.horizontalHeaderItem(0)
        item.setText(_translate("progressQuest", "Spell"))
        item = self.spellBookTable.horizontalHeaderItem(1)
        item.setText(_translate("progressQuest", "Level"))
        __sortingEnabled = self.spellBookTable.isSortingEnabled()
        self.spellBookTable.setSortingEnabled(False)
        self.spellBookTable.setSortingEnabled(__sortingEnabled)
        self.label_11.setText(_translate("progressQuest", "Equipment"))
        __sortingEnabled = self.equipmentTable.isSortingEnabled()
        self.equipmentTable.setSortingEnabled(False)
        self.equipmentTable.setSortingEnabled(__sortingEnabled)
        self.label_15.setText(_translate("progressQuest", "Inventory"))
        self.label_16.setText(_translate("progressQuest", "Encumbrance"))
        self.label_12.setText(_translate("progressQuest", "Plot Development"))
        self.label_17.setText(_translate("progressQuest", "Quests"))


class Main(QtWidgets.QWidget, Ui_progressQuest):
    def __init__(self):
        global lasttick, AllBars, AllLists
        super(Main, self).__init__()
        self.setupUi(self)

        AllBars = [ExpBar, PlotBar, TaskBar, QuestBar, EncumBar]
        AllLists = [Traits, Stats, Spells, Equips, Inventory, Plots, Quests]

        save = json.load(open("Upniem.json"))
        LoadGame(save)

        lasttick = timeGetTime()

        timer = QtCore.QTimer(self)
        timer.timeout.connect(Progress)
        timer.start(100)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = Main()
    window.show()
    sys.exit(app.exec_())
