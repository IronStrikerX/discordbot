import discord
import random
import os
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global game variables
players = []
roles_assigned = {}
captain_index = 0
current_team = []
votes = {}
mission_votes = {}
spy_list = []
mission_results = []
round_number = 1
MAX_ROUNDS = 5
game_channel = None  # set during game start

# VOTE VIEW
class VoteView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your vote.", ephemeral=True)
            return
        votes[self.user.id] = True
        await interaction.response.send_message("You voted to APPROVE the team.", ephemeral=True)
        self.stop()
        await check_all_votes(interaction)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your vote.", ephemeral=True)
            return
        votes[self.user.id] = False
        await interaction.response.send_message("You voted to REJECT the team.", ephemeral=True)
        self.stop()
        await check_all_votes(interaction)

# MISSION VIEW
class MissionView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user
        role = roles_assigned.get(user.id, "")
        if role != "Spy":
            self.children[1].disabled = True  # disable "Fail" for Resistance

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.success)
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your button!", ephemeral=True)
            return
        mission_votes[self.user.id] = "Pass"
        await interaction.response.send_message("You submitted a PASS.", ephemeral=True)
        self.stop()
        await check_all_mission_votes(interaction)

    @discord.ui.button(label="Fail", style=discord.ButtonStyle.danger)
    async def fail_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your button!", ephemeral=True)
            return
        mission_votes[self.user.id] = "Fail"
        await interaction.response.send_message("You submitted a FAIL.", ephemeral=True)
        self.stop()
        await check_all_mission_votes(interaction)

class GameModeView(View):
    def __init__(self, ctx, mentioned_players):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.mentioned_players = mentioned_players
        self.selection = None

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.blurple)
    async def normal(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the game starter can choose the mode.", ephemeral=True)
            return
        self.selection = "normal"
        self.stop()

    @discord.ui.button(label="Merlin", style=discord.ButtonStyle.green)
    async def merlin(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the game starter can choose the mode.", ephemeral=True)
            return
        self.selection = "merlin"
        self.stop()

# START COMMAND
@bot.command()
async def start(ctx, *args: discord.Member):
    global players

    global players, roles_assigned, spy_list, captain_index, round_number, game_channel
    mentioned = list(args)
    if len(mentioned) < 1 or len(mentioned) > 10:
        await ctx.send("Mention between 5 to 10 players to start.")
        return

    view = GameModeView(ctx, mentioned)
    await ctx.send(f"{ctx.author.mention}, choose the game mode:", view=view, ephemeral=True)
    await view.wait()

    if view.selection is None:
        await ctx.send("Timed out. Please try again.")
        return

    players[:] = mentioned
    round_number = 1
    captain_index = random.randint(0, len(players) - 1)
    game_channel = ctx.channel

    if view.selection == "normal":
        await assign_normal_roles(ctx)
    else:
        await assign_merlin_roles(ctx)

async def assign_normal_roles(ctx):
    spy_counts = {1: 1, 5:2, 6:2, 7:3, 8:3, 9:3, 10:4}
    num_spies = spy_counts[len(players)]

    roles = ["Spy"] * num_spies + ["Resistance"] * (len(players) - num_spies)
    random.shuffle(roles)

    roles_assigned.clear()
    spy_list.clear()

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
            await ctx.send(f"Couldn't DM {p.name}")

    await ctx.send(f"Normal Resistance game started. First Team Captain: **{players[captain_index].mention}**.\nUse `!team @p1 @p2 ...` to propose a mission team.")


async def assign_merlin_roles(ctx):
    # 5-player recommended: Merlin, Percival, Resistance, Morgana, Assassin
    special_roles = ["Merlin", "Percival", "Servant", "Morgana", "Assassin"]
    random.shuffle(special_roles)

    roles_assigned.clear()
    spy_list.clear()

    for p, r in zip(players, special_roles):
        roles_assigned[p.id] = r
        if r in ["Morgana", "Assassin"]:
            spy_list.append(p)

    for p in players:
        try:
            r = roles_assigned[p.id]
            if r == "Merlin":
                evil_players = [
                    discord.utils.get(ctx.guild.members, id=pid).name 
                    for pid, role in roles_assigned.items() 
                    if role in ["Morgana", "Assassin"]
                ]
                await p.send(f"You are **Merlin**.\nEvil players: {', '.join(evil_players)}")

            elif r == "Percival":
                targets = [pid for pid, role in roles_assigned.items() if role in ["Merlin", "Morgana"]]
                names = [discord.utils.get(ctx.guild.members, id=pid).name for pid in targets]
                await p.send(f"You are **Percival**.\nMerlin might be one of: {', '.join(names)}")

            elif r == "Morgana":
                others = [s.name for s in spy_list if s != p]
                await p.send(f"You are **Morgana**. Your fellow spy: {', '.join(others) if others else 'none'}")

            elif r == "Assassin":
                others = [s.name for s in spy_list if s != p]
                await p.send(f"You are **Assassin**. Your fellow spy: {', '.join(others) if others else 'none'}")

            else:
                await p.send("You are **Servant**.")
        except:
            await ctx.send(f"Couldn't DM {p.name}")

    await ctx.send(f"Avalon (Merlin) game started. First Team Captain: **{players[captain_index].mention}**.\nUse `!team @p1 @p2 ...` to propose a mission team.")



# COMMANDS

# TEAM COMMAND
@bot.command()
async def team(ctx, *mentions: discord.Member):
    if not players:  # No game active
        await ctx.send("No game running. Use `!start` first.", ephemeral=True)
        return

    global current_team, votes
    if ctx.author != players[captain_index]:
        await ctx.send("Only the current team captain can select a team.")
        return

    current_team = list(mentions)
    if not all(p in players for p in current_team):
        await ctx.send("All team members must be part of the game.")
        return

    votes.clear()
    if not ctx.interaction:  # Only send if not triggered by a button
        await ctx.send(f"------------------------------------- \n")
        await ctx.send(f"Team Captain: **{ctx.author.mention}** proposes:\n{', '.join(p.mention for p in current_team)}")
    

    for p in players:
        try:    
            await p.send("Do you approve this team?", view=VoteView(p))
        except:
            await ctx.send(f"Couldn't DM {p.name}")

#STATUS COMMAND
@bot.command()
async def status(ctx):
    if not players:
        await ctx.send("No game is currently running.")
        return

    mission_display = []
    for i, mission in enumerate(mission_results, start=1):
        passes = mission.count("Pass")
        fails = mission.count("Fail")
        result = "PASS" if fails == 0 else "FAIL"
        mission_display.append(f"**Mission {i}**: {passes} Pass, {fails} Fail → {result}")

    if not mission_display:
        mission_display = ["No missions have been run yet."]

    current_team_names = [p.mention for p in current_team] if current_team else ["No team proposed yet."]

    status_msg = (
        f"**Game Status**\n"
        f"➤ Round: {round_number} / 5\n"
        f"➤ Team Captain: {players[captain_index].mention}\n"
        f"➤ Current Team: {', '.join(current_team_names)}\n\n"
        f"**Mission History:**\n" + "\n".join(mission_display)
    )

    await ctx.send(status_msg)


#ENDGAME COMMAND
@bot.command()
async def endgame(ctx):
    global players, roles_assigned, captain_index, current_team, votes
    global mission_votes, spy_list, mission_results, round_number
    global game_channel

    # Reset all variables
    players.clear()
    roles_assigned.clear()
    captain_index = 0
    current_team.clear()
    votes.clear()
    mission_votes.clear()
    spy_list.clear()
    mission_results.clear()
    round_number = 1
    game_channel = None

    await ctx.send("Game reset. You can now start a new game.")

# CHECK ALL VOTES
async def check_all_votes(interaction):
    if len(votes) == len(players):
        approvals = sum(votes.values())
        channel = game_channel or interaction.channel

        # Group voters by choice
        approved = [p.mention for p in players if votes.get(p.id)]
        rejected = [p.mention for p in players if not votes.get(p.id)]

        # Send summary        
        if approvals > len(players) / 2:
            await channel.send("Team **Approved**. Sending mission DMs...")
            mission_votes.clear()
            for p in current_team:
                await p.send("You are on a mission. Choose your action:", view=MissionView(p))
        else:
            global captain_index
            await channel.send("Team **Rejected**. Passing captain.")
            captain_index = (captain_index + 1) % len(players)
            await channel.send(f"New Team Captain: **{players[captain_index].mention}**")

        await channel.send(
            f"Approved by: {', '.join(approved) if approved else 'No one'}\n"
            f"Rejected by: {', '.join(rejected) if rejected else 'No one'}"
        )


# CHECK MISSION RESULTS
async def check_all_mission_votes(interaction):
    global round_number, captain_index
    if len(mission_votes) == len(current_team):
        channel = game_channel or interaction.channel
        results = list(mission_votes.values())
        random.shuffle(results)
        mission_results.append(results)

        await channel.send(f"**Mission #{round_number} results:**")
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

        await channel.send(f"-------------------------------------\n")

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")

bot.run(TOKEN)
