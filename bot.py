import discord
import random
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

players = []
roles_assigned = {}
captain_index = 0
submitted_cards = []
current_team = []
votes = {}
mission_votes = {}
spy_list = []
mission_results = []
round_number = 1
MAX_ROUNDS = 5

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

game_channel = None

class VoteView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your vote.", ephemeral=True)
            return
        if interaction.user.id in votes:
            await interaction.response.send_message("You already voted.", ephemeral=True)
            return
        votes[interaction.user.id] = True
        await interaction.response.send_message("You voted to APPROVE the team.", ephemeral=True)
        self.stop()
        if len(votes) == len(players):
            await check_all_votes(interaction)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your vote.", ephemeral=True)
            return
        if interaction.user.id in votes:
            await interaction.response.send_message("You already voted.", ephemeral=True)
            return
        votes[interaction.user.id] = False
        await interaction.response.send_message("You voted to REJECT the team.", ephemeral=True)
        self.stop()
        if len(votes) == len(players):
            await check_all_votes(interaction)

class MissionView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user
        role = roles_assigned.get(user.id, "")
        if role != "Spy":
            self.children[1].disabled = True

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.success)
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your button!", ephemeral=True)
            return
        mission_votes[interaction.user.id] = "Pass"
        await interaction.response.send_message("You submitted a PASS.", ephemeral=True)
        self.stop()
        await check_all_mission_votes(interaction)

    @discord.ui.button(label="Fail", style=discord.ButtonStyle.danger)
    async def fail_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your button!", ephemeral=True)
            return
        mission_votes[interaction.user.id] = "Fail"
        await interaction.response.send_message("You submitted a FAIL.", ephemeral=True)
        self.stop()
        await check_all_mission_votes(interaction)

async def check_all_votes(interaction):
    if len(votes) == len(players):
        approvals = [p for p in players if votes.get(p.id) is True]
        rejections = [p for p in players if votes.get(p.id) is False]

        channel = interaction.channel

        if len(approvals) > len(players) / 2:
            await channel.send("Team approved. Sending mission options to team members.")
            mission_votes.clear()
            for p in current_team:
                await channel.send(f"{p.mention}, you are on a mission. Choose your action:", view=MissionView(p))
        else:
            global captain_index
            await channel.send("Team rejected. Captain passes to the next player.")
            captain_index = (captain_index + 1) % len(players)
            await channel.send(f"New Team Captain: {players[captain_index].mention}")

        vote_summary = "Voting Results:\n"
        vote_summary += f"Approve: {', '.join(p.mention for p in approvals)}\n"
        vote_summary += f"Reject: {', '.join(p.mention for p in rejections)}"
        await channel.send(vote_summary)


async def check_all_mission_votes(interaction):
    global round_number, captain_index

    if len(mission_votes) == len(current_team):
        # Use the saved game_channel, fallback to interaction.channel if None
        channel = game_channel or interaction.channel
        
        results = list(mission_votes.values())
        random.shuffle(results)
        mission_results.append(results)

        await channel.send(f"Mission #{round_number} results:")
        for r in results:
            await channel.send(r)

        round_number += 1

        if round_number > MAX_ROUNDS:
            await channel.send("Game over! The spies were:")
            for s in spy_list:
                await channel.send(f"{s.mention}")
        else:
            captain_index = (captain_index + 1) % len(players)
            await channel.send(f"Next Team Captain: **{players[captain_index].mention}**")

@bot.command()
async def start(ctx):
    global players, roles_assigned, spy_list, captain_index, round_number, game_channel
    game_channel = ctx.channel  # Save the channel where game was started
    mentioned = ctx.message.mentions
    if len(mentioned) < 1 or len(mentioned) > 10:   #the min and max amount of player 5-10
        await ctx.send("Mention between 5 to 10 players.")
        return

    players[:] = mentioned
    round_number = 1
    captain_index = random.randint(0, len(players) - 1)

    # Reset state
    roles_assigned.clear()
    spy_list.clear()
    votes.clear()
    mission_votes.clear()
    mission_results.clear()
    current_team.clear()

    spy_counts = {1:1, 3:2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4}
    num_spies = spy_counts[len(players)]

    roles = ["Spy"] * num_spies + ["Resistance"] * (len(players) - num_spies)
    random.shuffle(roles)

    for p, r in zip(players, roles):
        roles_assigned[p.id] = r
        if r == "Spy":
            spy_list.append(p)

    for p in players:
        try:
            if roles_assigned[p.id] == "Spy":
                others = [s.name for s in spy_list if s != p]
                msg = f"Your role is **Spy**. Spies: {', '.join(others)}" if others else "You are the only Spy."
            else:
                msg = "Your role is **Resistance**."
            await p.send(msg)
        except:
            await ctx.send(f"Couldn't DM {p.name}.")

    await ctx.send(f"Game started. Team Captain: **{players[captain_index].mention}**. Use `!team @p1 @p2 ...` to pick a mission team.")

@bot.command()
async def team(ctx, *mentions: discord.Member):
    global current_team, votes
    if ctx.author != players[captain_index]:
        await ctx.send("Only the current team captain can select a team.")
        return

    current_team = list(mentions)
    if not all(p in players for p in current_team):
        await ctx.send("All team members must be part of the game.")
        return

    votes.clear()
    await ctx.send(f"Team Captain: **{ctx.author.mention}** Proposed team: {', '.join(p.mention for p in current_team)}")
    for p in players:
        try:
            await p.send("Do you approve this team?", view=VoteView(p))
        except:
            await ctx.send(f"Couldn't DM {p.name}.")

@bot.event
async def on_ready():
    print(f" Logged in as {bot.user}")

bot.run(TOKEN)
