# coding=utf8
import sys, os, subprocess, time, datetime, math, pprint, traceback, operator, random
import Irc, Transactions, Blocknotify, Logger, Global, Hooks, Config
from Commands import parse_amount, validate_user
from collections import OrderedDict

games = {}

def check_gamble_timer(targetchannel, cmd_args, nick, source, acct, curtime, timer_min = 5, timer_max = 15, penalty_min = 10, penalty_max = 20):
	if targetchannel not in Global.gamble_list:
		return False
	if targetchannel not in Config.config["botchannels"]:
		timer_min = 60*timer_min
		timer_max = 60*timer_max
		penalty_min = 90*penalty_min
		penalty_max = 90*penalty_max
		str_botchannel = "Please use game commands in #RogerCasino. "
		is_admin = False
	else:
		str_botchannel = ""
		is_admin = Irc.is_admin(source)
		# if acct in Global.gamble_list[targetchannel] and Global.gamble_list[targetchannel][acct] > (curtime + timer_max + (penalty_max * 10) + (4*60*60)):
		# 	Global.gamble_list[targetchannel][acct] = curtime + timer_min + penalty_min
	if is_admin or acct not in Global.gamble_list[targetchannel]:
		return False
	if len(cmd_args) > 0 and nick in Global.response_read_timers:
		timer = 0
	else:
		timer = random.randint((timer_min),(timer_max))
	lastGambleTime = Global.gamble_list[targetchannel][acct]
	if lastGambleTime + timer > curtime:
		if lastGambleTime + timer > curtime + (timer_min/3) and lastGambleTime + timer < curtime + (40*24*60*60):
			penalty = random.randint((penalty_min),(penalty_max))
			Global.gamble_list[targetchannel][acct] = lastGambleTime + penalty
		timerApprx = random.randint(timer,timer+(30))
		difference = (lastGambleTime + timerApprx - curtime)/60
		if difference > 60:
			difference = difference/60
			timeUnit = "hours"
		else:
			timeUnit = "minutes"
		return "%s Help is available @ begambleaware.org. Wait %.1f %s." % (str_botchannel, difference, timeUnit)
	else:
		return False

def add_gamble_timer(targetchannel, acct, curtime):
	if targetchannel not in Global.gamble_list:
		Global.gamble_list[targetchannel] = {}
	Global.gamble_list[targetchannel][acct] = curtime

def add_read_timer(nick, time, cmd = "bj", vals = {}):
	Global.response_read_timers[nick] = {}
	Global.response_read_timers[nick]["vals"] = vals
	Global.response_read_timers[nick]["time"] = time
	Global.response_read_timers[nick]["cmd"] = cmd





def lotto(req, arg):
	"""%lotto <donation> <luckynumber> - Donate 'donation' (min 30) to pot for chance of winning a goldenshower (3000) if 'luckynumber' (0-100) picked (default 69)."""
	if len(arg) < 1:
		return req.reply(gethelp("lotto"))
	acct = Irc.account_names([req.nick])[0]
	host = Irc.get_host(req.source)
	minbet = 30
	chances = 1
	curtime = time.time()
	random.seed(curtime*1000)
	if "@Gamble_buildup" not in Global.gamble_list:
		Global.gamble_list["@Gamble_buildup"] = 0
	if host in Global.gamble_list and Global.gamble_list[host] != acct and not any(x.lower() == req.nick.lower() for x in Config.config["bridgebotnicks"]):
		Transactions.lock(acct, True)
	user_valid = validate_user(acct)
	if user_valid != True: return req.notice_private(user_valid)
	if req.target == req.nick and not Irc.is_admin(req.source):
		return req.reply("Can't lotto in private!")
	gamble_timer_reply = check_gamble_timer(targetchannel = req.target, cmd_args = arg, nick = req.nick, source = req.source, acct = acct, curtime = curtime, timer_min = 30, timer_max = 60, penalty_min = 20, penalty_max = 2*60)
	if gamble_timer_reply: return req.reply(gamble_timer_reply)
	toacct = req.instance
	try:
		amount = parse_amount(arg[0], acct)
	except ValueError as e:
		return req.notice_private(str(e))
	if len(arg) < 2:
		luckynumber = 69
	else:
		luckynumber = arg[1]
	if amount < minbet:
		return req.reply("Don't be so cheap! %s %s minimum!" % (minbet, Config.config["coinab"]), True)
	elif amount > (minbet * 5):
		chances = int(chances + (amount/100))
	if "@Gamble_buildup" in Global.gamble_list:
		if Global.gamble_list["@Gamble_buildup"] > 3000:
			multiplier = 2
		else:
			multiplier = 1
		Global.gamble_list["@Gamble_buildup"] = Global.gamble_list["@Gamble_buildup"] + amount
		chances = int(chances + (Global.gamble_list["@Gamble_buildup"]/(200/multiplier)))
	lotto=[]
	for i in range (chances):
		lotto.append(random.randint(1,100))
	token = Logger.token()
	try:
		Transactions.tip(token, acct, toacct, amount, tip_source = "@LOTTO")
		add_gamble_timer(targetchannel = req.target, acct = acct, curtime = curtime)
		Global.gamble_list[host] = acct
		if luckynumber in lotto: # or (Irc.is_admin(req.source) and luckynumber == random.randint(68,70)):
			if Transactions.balance(toacct) < parse_amount("goldenshower",toacct):
				return req.reply("We're all out of %s!!" % (Config.config["coinab"]), True)
			Global.gamble_list["@Gamble_buildup"] = 0
			req.say("%s played %i %s (%i%% chance) and WON a golden shower! Be moist and rejoice! Splashback! [%s]" % (req.nick, amount, Config.config["coinab"], chances, token))
			try:
				Transactions.tip(token, toacct, acct, parse_amount("goldenshower",toacct), tip_source = "@LOTTO") # accts swapped
			except Transactions.NotEnoughMoney:
				return req.notice_private("%s Bot ran out of winnings!" % (reply))
			soak(req, ["splashback", "1440"], from_instance = True)
		else:
			req.say("%s played %i %s but left everyone dry :( [%s]" % (req.nick, amount, Config.config["coinab"], token))
		return
	except Transactions.NotEnoughMoney:
		req.notice_private("You tried to play %i %s but you only have %i %s" % (amount, Config.config["coinab"], Transactions.balance(acct), Config.config["coinab"]))
		return



def bj_deal():
	deck = ['2♠', '3♠', '4♠', '5♠', '6♠', '7♠', '8♠', '9♠', '10♠', 'J♠', 'Q♠', 'K♠', 'A♠',
			'2♦', '3♦', '4♦', '5♦', '6♦', '7♦', '8♦', '9♦', '10♦', 'J♦', 'Q♦', 'K♦', 'A♦',
			'2♥', '3♥', '4♥', '5♥', '6♥', '7♥', '8♥', '9♥', '10♥', 'J♥', 'Q♥', 'K♥', 'A♥',
			'2♣', '3♣', '4♣', '5♣', '6♣', '7♣', '8♣', '9♣', '10♣', 'J♣', 'Q♣', 'K♣', 'A♣']
	random.shuffle(deck)
	phand = []
	dhand = []
	phand.append(deck.pop())
	dhand.append(deck.pop())
	phand.append(deck.pop())
	dhand.append(deck.pop())
	return dhand,phand,deck

def bj_total(hand, show_softhand = False):
	total = 0
	aceflag=False
	softhand=False
	for c in hand:
		card = c[:-3]
		if card == "J" or card == "Q" or card == "K":
			total+= 10
		elif card == "A":
			aceflag=True
			total+= 1
		else:
			total+= parse_amount(card)
	if aceflag and total<12:
		total+= 10
		softhand = True
	if show_softhand:
		return total, softhand
	return total

def bj_hit(hand, deck):
	card = deck.pop()
	hand.append(card)
	return hand,deck

def bj_result_string(dealer_hand, player_hand, player_total = False, hand_softhand = False, dealer_total = False):
	ptotal = ""
	dtotal = ""
	if hand_softhand:
		p_soft = "~"
	else:
		p_soft = ""
	if player_total:
		ptotal = " %s(%i)" % (p_soft, player_total)
	if dealer_total:
		dtotal = " (%i)" % (dealer_total)
		dealer_hand_mask = dealer_hand
	else:
		dealer_hand_mask = []
		for i in range(len(dealer_hand)):
			if i == 0: dealer_hand_mask.append(dealer_hand[i])
			else: dealer_hand_mask.append('??')
	dealer_hand_mask = '[ '+' '.join(card for card in dealer_hand_mask)+' ]'
	hand_mask = '[ '+' '.join(card for card in player_hand)+' ]'
	return hand_mask+ptotal+"  <->  House: "+dealer_hand_mask+dtotal

def bj_score(req, dealer_hand, player_hand, deal = False, stand = False, split = False, hand1 = False, force_dealerReveal = False):
	msg = False
	hand_win = False
	hand_draw = False
	hand_playon = False
	hand_payout_bj = False
	as_notice = False
	player_total, hand_softhand = bj_total(player_hand, show_softhand = True)
	dealer_total = bj_total(dealer_hand)
	dealerReveal = True
	if not player_total >= 21 and not dealer_total >= 21 and not stand:
		msg = "[H]it or [S]tand"
		if deal == True:
			if bj_total([player_hand[0]]) == bj_total([player_hand[1]]):
				msg = "[H]it , [S]tand , [D]ouble-down or S[P]lit"
			else:
				msg = "[H]it , [S]tand or [D]ouble-down"
		hand_playon = True
		dealerReveal = False
		as_notice = True
	elif player_total == 21 and deal == True:
		msg = "You got a BJ!!"
		hand_payout_bj = True
		hand_win = True
	elif dealer_total == 21 and deal == True:
		msg =  ":< Dealer got a BJ."
	elif player_total > 21:
		msg = ":< Bust."
	elif dealer_total > 21:	   
		msg = "Dealer busts!"
		hand_win = True
	elif player_total < dealer_total:
		msg =":< Beaten by Dealer"
	elif player_total > dealer_total:   
		msg = "Beat the Dealer!"
		hand_win = True
	elif player_total == dealer_total:   
		msg = ":S Draw"
		hand_draw = True
	if (dealerReveal and (not split or not hand1)) or (force_dealerReveal):
		results = bj_result_string(dealer_hand = dealer_hand, player_hand = player_hand, player_total = player_total, dealer_total = dealer_total)
	else:
		results = bj_result_string(dealer_hand = dealer_hand, player_hand = player_hand, player_total = player_total, hand_softhand = hand_softhand)
	if msg and split:
		if hand1:
			if not hand_playon and not force_dealerReveal:
				msg = "Switching to HAND2  ..."
			msg = "  (HAND1)  ...  %s" % (msg)
		else:
			msg = "  (HAND2)  ...  %s" % (msg)
	elif msg:
		msg = "  ...  %s" % (msg)
	else:
		msg = ""
	reply = results+msg
	return hand_win, reply, hand_playon, hand_draw, hand_payout_bj, as_notice

def bj_player_hit(player_hand, dealer_hand, deck, req, split, hand1 = False):
	player_hand, deck = bj_hit(player_hand, deck)
	while (not split or not hand1) and bj_total(player_hand) >= 21 and bj_total(dealer_hand) < 17:
		dealer_hand, deck = bj_hit(dealer_hand, deck)
	hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand, split = split, hand1 = hand1)
	return hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck, as_notice

def bj_player_stand(player_hand, dealer_hand, deck, req, split, hand1 = False, game_num = 1, force_dealerReveal = False):
	while (not split or not (hand1 and game_num == 1)) and bj_total(dealer_hand) < 17:
		dealer_hand, deck = bj_hit(dealer_hand, deck)
	hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand, split = split, stand = True, hand1 = hand1, force_dealerReveal = force_dealerReveal)
	return hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck

def bj_player_auto(player_hand, dealer_hand, deck, req, split, hand1 = False):
	while bj_total(player_hand) < 17:
		player_hand, deck = bj_hit(player_hand, deck)
	while (not split or not hand1) and bj_total(dealer_hand) < 17:
		dealer_hand, deck = bj_hit(dealer_hand, deck)
	hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand, split = split, stand = True, hand1 = hand1)
	return hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck

def hand_winner_tip(req, bet, pot_acct, winner_acct, token, hand_reply, hand_payout_bj = False):
	if hand_payout_bj:
		multiplier = 1.5
		odds = "(3to2)"
	else:
		multiplier = 1.0
		odds = "(1to1)"
	winnings = parse_amount(str(bet*multiplier),pot_acct, roundDown = True)
	try:
		Transactions.tip(token, pot_acct, winner_acct, (winnings+bet), tip_source = "@BLACKJACK")
		return req.reply("%s    WON %i %s %s!" % (hand_reply, winnings, Config.config["coinab"], odds))
	except Transactions.NotEnoughMoney:
		return req.reply("Bot ran out of winnings!")

def bj_cancel(token, bot_acct, player_acct, bet, bet2):
	msg = "Game cancelled, bet(s) partially refunded."
	if bet > 0:
		try:
			Transactions.tip(token, source = bot_acct, target = player_acct, amount = (bet/2), tip_source = "@BLACKJACK") #toacct swapped
		except Transactions.NotEnoughMoney:
			return req.notice_private("Bot ran out of money to return bet!")
	if bet2 > 0:
		try:
			Transactions.tip(token, source = bot_acct, target = player_acct, amount = (bet2/2), tip_source = "@BLACKJACK") #toacct swapped
		except Transactions.NotEnoughMoney:
			return req.notice_private("Bot ran out of money to return bet!")
	return msg

def bj(req, arg):
	"""%bj <bet> - Play Blackjack with 'bet' for chance to win 2x"""
	if len(arg) < 1:
		return req.reply(gethelp("bj"))
	if len(arg) > 1:
		conf_switch = arg[1]
	else:
		conf_switch = False
	acct = Irc.account_names([req.nick])[0]
	host = Irc.get_host(req.source)
	minbet = 10
	maxbet = 1000
	# if not Irc.is_admin(req.source):
	# 	return # temporary disable
	if host in Global.gamble_list and Global.gamble_list[host] != acct and not any(x.lower() == req.nick.lower() for x in Config.config["bridgebotnicks"]):
		Transactions.lock(acct, True)
	user_valid = validate_user(acct)
	if user_valid != True: return req.notice_private(user_valid)
	if req.target == req.nick and not Irc.is_admin(req.source):
		return req.reply("Can't bj in private!")
	if req.nick in Global.response_read_timers and not Global.response_read_timers[req.nick]["cmd"] == "bj":
		return req.notice_private("One game at a time!")
	curtime = time.time()
	random.seed(curtime*1000)
	gamble_timer_reply = check_gamble_timer(targetchannel = req.target, cmd_args = arg, nick = req.nick, source = req.source, acct = acct, curtime = curtime, timer_min = 4, timer_max = 8, penalty_min = 5, penalty_max = 15)
	if gamble_timer_reply: return req.reply(gamble_timer_reply)
	toacct = req.instance
	choice = arg[0].lower()
	token = Logger.token()
	Logger.log("c","BJ triggered: %s" % (arg))
	if len(arg) > 0 and not (arg[0].isdigit() and parse_amount(arg[0]) >= 5) and req.nick in Global.response_read_timers:
		Logger.log("c","BJ stored vals: %s" % (Global.response_read_timers[req.nick]["vals"]))
		bj_start = Global.response_read_timers[req.nick]["vals"]["bj_start"]
		bj_public = Global.response_read_timers[req.nick]["vals"]["bj_public"]
		deck = Global.response_read_timers[req.nick]["vals"]["deck"]
		dealer_hand = Global.response_read_timers[req.nick]["vals"]["dealer_hand"]
		player_hand = Global.response_read_timers[req.nick]["vals"]["player_hand"]
		bet = Global.response_read_timers[req.nick]["vals"]["bet"]
		player_hand2 = Global.response_read_timers[req.nick]["vals"]["player_hand2"]
		bet2 = Global.response_read_timers[req.nick]["vals"]["bet2"]
		game_num = Global.response_read_timers[req.nick]["vals"]["game_num"]
		hand_win = Global.response_read_timers[req.nick]["vals"]["hand_win"]
		hand_draw = Global.response_read_timers[req.nick]["vals"]["hand_draw"]
		hand2_reply = hand_reply = ""
		choiceFound = hand_playon = hand2_playon = hand_payout_bj = hand2_payout_bj = hand2_win = hand2_draw = as_notice = False
		if bet2 > 0:
			bj_split = True
		else:
			bj_split = False
		if bj_split and game_num == 2:
			if choice == "hit" or choice == "h" or choice == "h2" or choice == "1":
				choiceFound = True
				hand2_win, hand2_reply, hand2_playon, hand2_draw, hand2_payout_bj, player_hand2, dealer_hand, deck, as_notice = bj_player_hit(player_hand = player_hand2, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split)
			elif choice == "stand" or choice == "s" or choice == "s2" or choice == "2":
				choiceFound = True
				hand2_win, hand2_reply, hand2_playon, hand2_draw, hand2_payout_bj, player_hand2, dealer_hand, deck = bj_player_stand(player_hand = player_hand2, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split)
			elif (len(arg) == 1 and choice == "auto") or choice == "auto" or choice == "auto2":
				choiceFound = True
				hand2_win, hand2_reply, hand2_playon, hand2_draw, hand2_payout_bj, player_hand2, dealer_hand, deck = bj_player_auto(player_hand = player_hand2, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split)
			else:
				choice = "none"
		elif choice == "hit" or choice == "h" or choice == "h1" or choice == "1":
			choiceFound = True
			hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck, as_notice = bj_player_hit(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True)
		elif choice == "stand" or choice == "s" or choice == "s1" or choice == "2":
			choiceFound = True
			hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck = bj_player_stand(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True)
		elif choice == "auto" or choice == "auto1":
			choiceFound = True
			hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck = bj_player_auto(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True)
		elif bj_start and (choice == "d" or choice == "dd" or choice == "doubledown" or choice == "3"):
			choiceFound = True
			try:
				Transactions.tip(token, acct, toacct, bet, tip_source = "@BLACKJACK")
				bet = bet + bet
				hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck, as_notice = bj_player_hit(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True)
				hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck = bj_player_stand(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True)
			except Transactions.NotEnoughMoney:
				return req.notice_private("You tried to double down %i %s but you only have %i %s" % (bet, Config.config["coinab"], Transactions.balance(acct), Config.config["coinab"]))
		elif bj_start and (choice == "split" or choice == "p" or choice == "4") and (bj_total([player_hand[0]]) == bj_total([player_hand[1]])):
			choiceFound = True
			try:
				Transactions.tip(token, acct, toacct, bet, tip_source = "@BLACKJACK")
				bet2 = bet
				bj_split = True
				player_hand2 = [player_hand.pop(1)]
				player_hand, deck = bj_hit(player_hand, deck)
				player_hand2, deck = bj_hit(player_hand2, deck)
				hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand, split = bj_split, hand1 = True)
			except Transactions.NotEnoughMoney:
				return req.notice_private("You tried to split on %i %s but you only have %i %s" % (bet, Config.config["coinab"], Transactions.balance(acct), Config.config["coinab"]))
		else:
			choice = "none"
		if choiceFound: Global.response_read_timers.pop(req.nick)
		if bj_split and game_num == 1 and not hand_playon:
			game_num = 2
			hand2_playon = True
			hand2_win, hand2_reply, hand_playon, hand2_draw, hand2_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand2, split = bj_split)
		if game_num == 2 and not hand_playon and not hand2_playon:
			hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck = bj_player_stand(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = bj_split, hand1 = True, game_num = game_num, force_dealerReveal = True)
		if bet > 0 and hand_win and not hand_playon and not hand2_playon:
			hand_winner_tip(req, bet = bet, pot_acct = toacct, winner_acct = acct, token = token, hand_reply = hand_reply, hand_payout_bj = hand_payout_bj)
			bet = 0
			hand_reply = ""
			if bet2 == 0: return
		if bet2 > 0 and hand2_win and not hand_playon and not hand2_playon and game_num == 2:
			hand_winner_tip(req, bet = bet2, pot_acct = toacct, winner_acct = acct, token = token, hand_reply = hand2_reply, hand_payout_bj = hand2_payout_bj)
			bet2 = 0
			if bet == 0 and bet2 == 0: return
		if choiceFound and (not hand_win or not hand2_win) and (bet > 0 or bet2 > 0):
			if hand_playon or hand2_playon:
				add_read_timer(nick = req.nick, time = curtime, cmd = "bj", vals = {"bj_start":False, "bj_public":bj_public, "deck":deck, "hand_win":hand_win, "hand_draw":hand_draw, "dealer_hand":dealer_hand, "player_hand":player_hand, "bet":bet, "player_hand2":player_hand2, "bet2":bet2, "game_num":game_num })
			elif hand_draw and bet > 0:
				try:
					Transactions.tip(token, toacct, acct, bet, tip_source = "@BLACKJACK") #toacct swapped
					hand_reply = "%s bet returned." % (hand_reply)
				except Transactions.NotEnoughMoney:
					return req.notice_private("Bot ran out of money to return bet!")
			if not hand_playon and not hand2_playon and not hand_draw and choice == "none":
				cancelmsg = bj_cancel(token = token, bot_acct = toacct, player_acct = acct, bet = bet, bet2 = bet2)
				return req.notice_private("%s  %s" % hand_reply, cancelmsg)
			if len(hand_reply) > 2 and as_notice and req.target not in Config.config["botchannels"] and not bj_public:
				req.notice_private(hand_reply)
			elif len(hand_reply) > 2:
				req.reply(hand_reply)
			if bet2 > 0:
				if hand2_draw:
					try:
						Transactions.tip(token, toacct, acct, bet2, tip_source = "@BLACKJACK") #toacct swapped
						hand2_reply = "%s bet returned." % (hand2_reply)
					except Transactions.NotEnoughMoney:
						return req.notice_private("Bot ran out of money to return bet!")
				if len(hand2_reply) > 2 and as_notice and req.target not in Config.config["botchannels"] and not bj_public:
					req.notice_private(hand2_reply)
				elif len(hand2_reply) > 2:
					req.reply(hand2_reply)
	elif req.nick not in Global.response_read_timers or (req.nick in Global.response_read_timers and Global.response_read_timers[req.nick]["time"] + (5*60) < curtime) or (arg[0].isdigit() and parse_amount(arg[0]) >= minbet):
		try:
			amount = parse_amount(arg[0], acct)
		except ValueError as e:
			return req.notice_private(str(e))
		if req.nick in Global.response_read_timers and Global.response_read_timers[req.nick]["cmd"] == "bj":
			cancelmsg = bj_cancel(token = token, bot_acct = toacct, player_acct = acct, bet = Global.response_read_timers[req.nick]["vals"]["bet"], bet2 = Global.response_read_timers[req.nick]["vals"]["bet2"])
			req.notice_private(cancelmsg)
			Global.response_read_timers.pop(req.nick)
		if amount < minbet:
			return req.reply("Don't be so cheap! %s %s minimum!" % (minbet, Config.config["coinab"]), True)
		elif amount > maxbet:
			return req.reply("Can't let you BJ that many %s at once." % (Config.config["coinab"]), True)
		if conf_switch == "public":
			bj_public = True
		else:
			bj_public = False
		try:
			Transactions.tip(token, acct, toacct, amount, tip_source = "@BLACKJACK")
			add_gamble_timer(targetchannel = req.target, acct = acct, curtime = curtime)
			Global.gamble_list[host] = acct
			choice = 0
			dealer_hand, player_hand, deck = bj_deal()
			if conf_switch == "auto" and not bj_total(dealer_hand) == 21 and not bj_total(player_hand) == 21:
				as_notice = False
				hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, player_hand, dealer_hand, deck = bj_player_auto(player_hand = player_hand, dealer_hand = dealer_hand, deck = deck, req = req, split = False, hand1 = True)
			else:
				hand_win, hand_reply, hand_playon, hand_draw, hand_payout_bj, as_notice = bj_score(req, dealer_hand, player_hand, deal = True)
			if hand_playon:
				add_read_timer(nick = req.nick, time = curtime, cmd = "bj", vals = {"bj_start":True, "bj_public":bj_public, "deck":deck, "hand_win":False, "hand_draw":False, "dealer_hand":dealer_hand, "player_hand":player_hand, "bet":amount, "player_hand2":[], "bet2":0, "game_num":1 })
			elif hand_win:
				return hand_winner_tip(req, bet = amount, pot_acct = toacct, winner_acct = acct, token = token, hand_reply = hand_reply, hand_payout_bj = hand_payout_bj)
			if as_notice and req.target not in Config.config["botchannels"] and not bj_public:
				return req.notice_private(hand_reply)
			else:
				return req.reply(hand_reply)
		except Transactions.NotEnoughMoney:
			req.notice_private("You tried to play %i %s but you only have %i %s" % (amount, Config.config["coinab"], Transactions.balance(acct), Config.config["coinab"]))
			return
	else:
		return req.notice_private("One game at a time!")


def roulette_roll(bet_choice, landon):
	roul_win = False
	roul_multiplier = 0
	red_nums = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
	black_nums = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
	topline_nums = [0, 1, 2, 3]
	if landon > 0 and ((bet_choice == 'even' and landon % 2 == 0) or (bet_choice == 'odd' and landon % 2 == 1) or (bet_choice == 'low' and landon < 19) or (bet_choice == 'high' and landon >= 19)):
		roul_win = True
		roul_multiplier = 2
	elif landon > 0 and (((bet_choice == '1st' or bet_choice == 'first') and landon < 13) or ((bet_choice == '2nd' or bet_choice == 'second') and landon >= 13 and landon <= 25) or ((bet_choice == '3rd' or bet_choice == 'third') and landon > 25)):
		roul_win = True
		roul_multiplier = 3
	elif landon > 0 and ((bet_choice == 'red' and landon in red_nums) or (bet_choice == 'black' and landon in black_nums)):
		roul_win = True
		roul_multiplier = 2
	elif (bet_choice == 'topline' and landon in topline_nums) or (bet_choice == 'basket' and landon in topline_nums):
		roul_win = True
		roul_multiplier = 9
	elif bet_choice.isdigit():
		bet_choice_num = parse_amount(bet_choice, min_amount = 0)
		if bet_choice_num >= 0 and bet_choice_num <= 36 and bet_choice_num == landon:
			roul_win = True
			roul_multiplier = 36
	return roul_win, roul_multiplier


def roulette(req, arg):
	"""%roul <bet_amt1> <bet1> [ <bet_amt2> <bet2> ... ] - Play Roulette with 'bet_amt' and a 'bet'"""
	if len(arg) < 2 or not len(arg) % 2 == 0:
		return req.reply(gethelp("roul"))
	bet_count = len(arg)/2
	acct = Irc.account_names([req.nick])[0]
	host = Irc.get_host(req.source)
	minbet = 10
	maxbet = 1000
	won_bet_count = 0
	lost_bets = 0
	total_bet_amt = 0
	roul_valid_bets = ["even","odd","1st","2nd","3rd","first","second","third","low","high","red","black","topline","basket"]
	curtime = time.time()
	random.seed(curtime*1000)
	# if not Irc.is_admin(req.source):
	# 	return # temporary disable
	if host in Global.gamble_list and Global.gamble_list[host] != acct and not any(x.lower() == req.nick.lower() for x in Config.config["bridgebotnicks"]):
		Transactions.lock(acct, True)
	user_valid = validate_user(acct)
	if user_valid != True: return req.notice_private(user_valid)
	if req.target == req.nick and not Irc.is_admin(req.source):
		return req.reply("Can't roulette in private!")
	gamble_timer_reply = check_gamble_timer(targetchannel = req.target, cmd_args = arg, nick = req.nick, source = req.source, acct = acct, curtime = curtime, timer_min = 5, timer_max = 10, penalty_min = 10, penalty_max = 20)
	if gamble_timer_reply: return req.reply(gamble_timer_reply)
	toacct = req.instance
	token = Logger.token()
	for i in range(bet_count):
		argoffset = i+i
		bet_choice = arg[(1+argoffset)].lower()
		if bet_choice not in roul_valid_bets and not bet_choice.isdigit():
			# return req.reply(gethelp("roul"))
			return req.reply("Invalid bet, available bets: %s" % (roul_valid_bets))
		try:
			bet = parse_amount(arg[(0+argoffset)], acct)
		except ValueError as e:
			return req.notice_private(str(e))
		total_bet_amt = total_bet_amt + bet
	if total_bet_amt < minbet:
		return req.reply("Don't be so cheap! %s %s minimum!" % (minbet, Config.config["coinab"]), True)
	elif total_bet_amt > maxbet:
		return req.reply("Can't let you spin that many %s at once." % (Config.config["coinab"]), True)
	add_gamble_timer(targetchannel = req.target, acct = acct, curtime = curtime)
	Global.gamble_list[host] = acct
	landon = random.randint(0, 36)
	reply = "Fondling balls... landed on %i" % (landon)
	try:
		Transactions.tip(token, acct, toacct, total_bet_amt, tip_source = "@ROULETTE")
		for i in range(bet_count):
			argoffset = i+i
			bet = parse_amount(arg[(0+argoffset)], acct)
			bet_choice = arg[(1+argoffset)].lower()
			roul_win, roul_multiplier = roulette_roll(bet_choice, landon)
			if roul_win:
				won_bet_count = won_bet_count + 1
				roul_winnings = parse_amount(str(bet*roul_multiplier),toacct, roundDown = True)
				if bet_count > 1 and won_bet_count > 1:
					reply = "%s + %i on %s" % (reply, (roul_winnings-bet), bet_choice.upper())
				else:
					reply = "%s ... You WON %i %s on %s" % (reply, (roul_winnings-bet), Config.config["coinab"], bet_choice.upper())
				try:
					Transactions.tip(token, toacct, acct, roul_winnings, tip_source = "@ROULETTE") # accts swapped
				except Transactions.NotEnoughMoney:
					return req.notice_private("%s Bot ran out of winnings!" % (reply))
			else:
				if bet_count > 3:
					lost_bets = lost_bets + bet
				else:
					reply = "%s ... You lost %i %s on %s :<" % (reply, bet, Config.config["coinab"], bet_choice.upper())
	except Transactions.NotEnoughMoney:
		return req.notice_private("%s You tried to play %i %s but you only have %i %s" % (reply, total_bet_amt, Config.config["coinab"], Transactions.balance(acct), Config.config["coinab"]))
	if lost_bets > 0:
		reply = "%s ... You lost %i %s on poor choices :<" % (reply, lost_bets, Config.config["coinab"])
	return req.reply(reply)


games["lotto"] = lotto
games["lottery"] = lotto
games["gamble"] = lotto

games["bj"] = bj
games["blackjack"] = bj
games["21"] = bj

games["roul"] = roulette
games["roulette"] = roulette
games["ballfondle"] = roulette
games["fondleballs"] = roulette




def gethelp(name):
	if name[0] == Config.config["prefix"]:
		name = name[1:]
	cmd = games.get(name, None)
	if cmd and cmd.__doc__:
		return cmd.__doc__.split("\n")[0].replace("%", Config.config["prefix"])