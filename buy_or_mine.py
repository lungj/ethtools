#!/usr/bin/env python3
'''Author: jonathan lung (https://github.com/lungj)
Maybe I just stopped you from doing something foolish. Or in retrospect brilliant (d'oh).
In any case...
ETH/ETC: 0xc5500095A395B4FB3ba81bB0D8e316c675d1F47C

Data sourced from https://etherscan.io

THIS PROGRAM DOES NOT CONSTITUTE INVESTMENT ADVICE. IT IS OFFERED AS-IS AND WITHOUT
WARRANTY. See LICENSE file.

Program for comparing how much ETH one would hold if one had been mining vs.
buy-and-holding Ethereum.

Ignores the existence of Ethereum Classic and exchange fees.
Including Ethereum Classic makes GPU mining seem less profitable in comparison.
Also excludes the residual value of mining equipment and the added liquidity of holding
ether versus mining equipment.
'''

import csv
import datetime
import urllib.request
from math import ceil, log

EXTRAPOLATION_DAYS = 0    # Extrapolate n days into the future using 2 * n days of history.
                          # Fit using simple discrete exponent. Sensitive to spikes on a single day.
                          # Obviously does not predict the future. Thus, it will fail to account for
                          # significant events like
                          # * technological events (e.g., switch to proof-of-stake or cheap efficient mining equipment)
                          # * legal events (e.g., regulatory changes, acceptance of crypto for tax payments)
                          # * economic events (e.g., collapse of the US dollar or a country adopting a
                          #                    crypto currency as their national currency)
                          # * natural disasters (such as ones causing GPU supply constraints)
                          # * social events (e.g., crypto-stigma like after Silk Road)
                          #
                          # It also does not factor in things like
                          # * inability for users to secure their wallets, resulting in theft
                          # * misconfiguration of systems, resulting in lost ether
                          # * bad backups resulting in loss (especially if you trigger a fire with an
                          #                                  unsafe rig!)
                          # * change in rewards algorithm (the ice age is only factored in partly into the calculations)
                          # * running the wrong software (such as after the DAO-related hard fork)

NUM_GPUs = 4
GPUs_PER_SYSTEM = 4       # Number of GPUs you can cram into a rig.
GPU_HASHRATE = 30e6       # Hashes per second.
GPU_WATTS = 275           # Watts consumed by GPU.
BASE_WATTS = 80           # Watts consumed by the rest of the system (this number is often high, like this, with lower-cost MOBO/CPU).
UNCLE_RATE = 0.1          # Approximately 10% of blocks (recently) have been uncles.
                          # There were far more uncles on the first day of mining, when difficulty was very low relative to network
                          # hash rate; the actual profitability of mining on day 1 is thus overestimated by this program.
AVERGE_UNCLE_REWARD = 0.6 # An estimate of the average uncle reward, relative to a full block reward.

MINING_FEES = 0.02        # Amount paid to pools, etc.
EFFICIENCY = 0.92         # Uptime of rigs. Impacted by things like power outages, system instability, network outages,
                          # hardware failure (+ replacement time), software configuration problems, etc.
                          # 92% is probably reasonable for someone who knows what they're doing and isn't spending a boatload
                          # of money on getting extra 9s of reliability and using a pool (which may be subject to a DOS).
                          # Also throws in some efficiency-loss to account for pool mining software accounting.
                          # Also assumes you aren't physically able to fix rigs 24/7.
                          # You're sleeping for about 1/4 of the day, let alone going to work!
                          # I assume your power consumption goes to 0 whenever you experience downtime, but this is not
                          # true for system hangs and network outages.

# Assume a high-quality PSU that under-specifies the PSU's **continuous** wattage output.
PSU_WATTAGE = 750         # Wattage of a single PSU when new.
PSU_SAFETY_FACTOR = 1.2   # A high-quality PSU can often **continuously** deliver a bit more than its rated power.
                          # Low-quality PSUs might not even be able to deliver their rated capacity continuously.
                          # Safety factor of 1.2 means a 100W PSU can deliver 120W safely (or shut down at that level); this
                          # makes capacitor aging less of an issue.
PSU_CAPACITOR_AGING = 0.9 # Loss of 10% of PSU capacity per year, assuming PSU is not fully loaded.
PSU_LOADING_FINAL = 0.9   # PSU loading (as percent of degraded capacity at the end of simulation period).
                          # Need leeway to prevent fires and maintain reliability!
PSU_EFFICIENCY = 0.9      # 90% is probably a little generous for the PSU price I listed.

SALES_TAX = 0.13          # Sales tax (13%) in Ontario, Canada.
ELECTRICITY_PRICE = 0.11  # Price of a kWh of electricity, including delivery charges and taxes, in Toronto,
                          # in USD, averaged over a year at 24/7 deliver.
                          # Note that even as "free heat", electric may be more expensive than alternatives -- and
                          # you need to distribute the heat or else the heat bleeds less efficiently than other heating.
                          # Certainly, much less efficient than space heating in large spaces.
                          # I made the simplifying assumption that the cash used for electricity is used, up-front,
                          # to purchase Ethereum, rather than spread over time.
                          
AC_PCT = 0.20             # Percent of the year you run an air conditioner. The cost is amortized in the calculator for simplicity.
                          
# The rest of these values are automatically generated/cannot/should not be tweaked.
BLOCK_REWARD = 5          # Number of ether awarded per mined block.
SYSTEM_AGE = datetime.datetime.now().year - 2015 # Simplified -- even new rigs are provisioned for extended life.
RIG_HASHRATE = GPU_HASHRATE * NUM_GPUs

SYSTEM_WATTS = BASE_WATTS + GPU_WATTS * NUM_GPUs
# Amount of watts, as a percent of rated spec, that the PSU can actually deliver over time.
PSU_CAPACITY_EFFECTIVE = max(PSU_CAPACITOR_AGING ** SYSTEM_AGE / PSU_SAFETY_FACTOR, 1)
NUM_PSUs = ceil((SYSTEM_WATTS) / PSU_CAPACITY_EFFECTIVE / PSU_LOADING_FINAL / PSU_WATTAGE) # Assume spare GPUs purchased up front to minimize downtime.

DAILY_KWH = (SYSTEM_WATTS / PSU_EFFICIENCY * 24 / 1000) * (1 + AC_PCT / 3) # Number of kWh consumed per day by rig + AC, amortized

# Assume an open-air rig using scavanged parts, so no case needs to be factored in to price.
RIG_COMPONENTS = {
					'GPUs': 330 * NUM_GPUs, # R9 390s based on https://forums.nexusmods.com/index.php?/topic/3046214-r9-390-is-the-new-priceperformance-king/
				  	'CPU + MOBO + RAM': 200 * ceil(GPUs_PER_SYSTEM / NUM_GPUs),
				  	'PSUs': 100 * NUM_PSUs,
				  	'Misc': 100 * ceil(GPUs_PER_SYSTEM / NUM_GPUs),
				  	}

RIG_PRICE = sum(RIG_COMPONENTS.values()) * (1 + SALES_TAX)


def opener(url):
	'''Get data from the web.'''
	request = urllib.request.Request(url=url,
								 data=None,
								 headers={
									'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko) Version/10.1.1 Safari/603.2.4'
								})

	conn = urllib.request.urlopen(request)
	
	conn.readline() # Ignore header line
	data = [line.decode('utf-8') for line in conn.readlines()]
	conn.close()
	return data
	
	

def gen_table():
	'''Return a list of lists of unix epochs, prices, and difficulty.'''

	# Get date-to-price list
	prices_reader = csv.reader(opener('https://etherscan.io/chart/etherprice?output=csv'))
	prices = [(int(unix_epoch), float(price)) for (_, unix_epoch, price) in prices_reader]

	# Get date-to-difficulty list
	difficulty_reader = csv.reader(opener('https://etherscan.io/chart/difficulty?output=csv'))
	difficulty = [(int(unix_epoch), float(difficulty) * 1e12) for (_, unix_epoch, difficulty) in difficulty_reader]

	assert len(prices) == len(difficulty), 'Different number of data points in file.'

	# Create final table/list.
	table = []
	for idx in range(len(prices)):
		assert prices[idx][0] == difficulty[idx][0], 'Dates do not line up in data files.'
		table.append(prices[idx] + difficulty[idx][1:])

	if EXTRAPOLATION_DAYS:
		avg_price_daily_change_pct = (table[-1][1] / table[-EXTRAPOLATION_DAYS][1]) ** (1 / EXTRAPOLATION_DAYS)
		avg_diff_daily_change_pct = (table[-1][2] / table[-EXTRAPOLATION_DAYS][2]) ** (1 / EXTRAPOLATION_DAYS)

		for i in range(EXTRAPOLATION_DAYS):
			new_date = table[-1][0] + 24 * 60 * 60 # Calculate next day's UNIX epoch.
			new_price = table[-1][1] * avg_price_daily_change_pct
			new_diff = table[-1][2] * avg_diff_daily_change_pct
			table.append((new_date, new_price, new_diff))

	return table
			
if __name__ == '__main__':
	data = gen_table()
	
	cumulatively_mined_ether = 0 # Total ether mined in period
	cumulative_energy_use = 0    # Number of kWh used.
	cumulative_cost = RIG_PRICE
	
	print(__doc__)
	print('Date       Cumulatively        Purchased          Total       German         Purchase')
	print('           mined                                  cost        household      % of')
	print('           ETH                 ETH                (USD)       equiv          mining')
	for (unix_epoch, price, difficulty) in data[::-1]:
		date = datetime.datetime.fromtimestamp(unix_epoch).strftime('%Y-%m-%d')
		cumulatively_mined_ether += BLOCK_REWARD / (difficulty / RIG_HASHRATE / 24 / 60 / 60) * (1 - UNCLE_RATE + UNCLE_RATE * AVERGE_UNCLE_REWARD) * (EFFICIENCY - MINING_FEES)
		cumulative_cost += ELECTRICITY_PRICE * DAILY_KWH
		purchased_ether = cumulative_cost / (price or 1)
		cumulative_energy_use += DAILY_KWH
		print('%(date)s %(mined) 12.3f%(minebet)s    %(purchased) 12.3f%(buybet)s    %(cost) 10.2f    %(household) 12.2f  %(ratio)11.2f%%' % {
			'date': date,
			'mined': cumulatively_mined_ether,
			'purchased': purchased_ether,
			'cost': cumulative_cost,
			'household': cumulative_energy_use / 3512,
			'minebet': ' *'[cumulatively_mined_ether > purchased_ether],
			'buybet': ' *'[cumulatively_mined_ether < purchased_ether],
			'ratio': purchased_ether / cumulatively_mined_ether * 100,
			})
	print('''German household equiv is the number of average houses in Germany
that could powered for a year for the amount of power being consumed.
http://shrinkthatfootprint.com/average-household-electricity-consumption

PLEASE DON'T KILL OUR PLANET. Even if you don't think climate change is brought about by
humans, there is finite energy and materials on this planet. A lot of energy and material
goes into producing electronics (99% of material is discarded as waste; in contrast,
almost all of the input materials for a gas-burning car go into the final product).
That's not to say don't mine... just think about what you're really doing.

Purchaes % of mining is how much ETH you'd have, relative to mining, if you bought
ETH on this day.
''')
