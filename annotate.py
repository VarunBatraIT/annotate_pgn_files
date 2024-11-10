# annotate.py

# This script `annotate.py` is licensed for personal and academic use only. Any commercial use, 
# distribution, or modification is prohibited without prior written permission from 
# the author.

# If you wish to use `annotate.py` for commercial purposes, please contact codevarun@gmail.com


import chess.pgn
import json
from pathlib import Path
import os

# read debug from env
debug = False
if "DEBUG" in os.environ:
    debug = os.environ["DEBUG"]
    if debug.lower() == "true":
        debug = True
    else:
        debug = False
print (f"Debug: {debug}")
max_variations = 3
max_variations_depth = 5
pgn_positions = {}

def load_evaluations(evaluation_file_path, pgn_positions):
    evals = {}
    found_positions = 0  # To track how many positions have been found
    total_positions = len(pgn_positions)
    print(f"Loading evaluations from: {evaluation_file_path}")
    
    with open(evaluation_file_path, 'r') as f:
        # Debug total_lines
        total_lines = 1000000
        if not debug:
            total_lines = sum(1 for line in f)  # Count the total number of lines
        f.seek(0)  # Rewind to the beginning of the file
        loaded_lines = 0
        
        for line in f:
            data = json.loads(line)
            position = data['fen']
            # If the position is in PGN positions, process it
            if position in pgn_positions:
                found_positions += 1
                # Check if there are evaluations available
                evals[position] = data;
                # Stop loading further once we've found evaluations for all required positions
                if found_positions == total_positions:
                    print("All positions found in evaluations, stopping the loading.")
                    break
            
            loaded_lines += 1
            if loaded_lines % (total_lines // 100) == 0:
                print(f"Loading evaluations: {int((loaded_lines / total_lines) * 100)}%")
                print(f" Position found: {found_positions} / {total_positions}")

            if found_positions > 500 and debug:
                print(f"Debug Early Return")
                return evals
    
    print(f"Finished loading evaluations. Found {len(evals)} evaluations.")
    return evals

def generate_fens_from_pgn(pgn_file_path):
    
    # Load fens and keep number of times they appear
    fens = {}
    print(f"Generating FENs from PGN file: {pgn_file_path}")
    number_of_pgn_processed = 0
    with open(pgn_file_path, 'r') as pgn_file:
        # Iterate over all games in the PGN file
        while (game := chess.pgn.read_game(pgn_file)) is not None:
            board = game.board()  # Start with an empty board for each game
            for move in game.mainline_moves():
                # Generate FEN and modify the last two parts (half-move clock and full move number)
                fen = board.fen()
                fen = fen_modify(fen)
                # Join and clean up spaces
                fens[fen] = fens.get(fen, 0) + 1
                board.push(move)
            fen = board.fen()
            fen = fen_modify(fen)
            fens[fen] = fens.get(fen, 0) + 1
            number_of_pgn_processed += 1
            if number_of_pgn_processed % 1000 == 0:
                print(f"Processed {number_of_pgn_processed} games")
            if debug and number_of_pgn_processed > 1000:
                print(f"Debug Early Return")
                return fens
    
    # Print the total unique positions and the top 10 FENs
    print(f"Total unique positions (FENs) to annotate: {len(fens)}")
    print("Top 10 FENs:")
    for fen, count in sorted(fens.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"{fen} - {count} times")

    return fens
def fen_modify(fen):
    fen = fen.split(" ")
    fen[-2:] = ['', '']  # Replace the half-move clock and full move number
    fen = ' '.join(fen).strip() 
    return fen
def get_visits_from_node(node):
    global pgn_positions
    ## Returns 0 for start of the game
    if node.board().fullmove_number == 1 and node.board().turn == chess.WHITE:
        return 0
    ## Get fen from node and node could be a variation
    fen = node.board().fen()
    fen = fen_modify(fen)
    # Print fen
    visits = pgn_positions.get(fen, 0)
    return visits

def add_variations_to_node(node, move_evals):
    ## Get fen from node
    ## Add the evaluations as a comment to the move
    ## Add the evals and move to the node
    if move_evals:
        if "evals" in move_evals:
            move_evals = move_evals["evals"]
            ## Keeping max/max few depth evaluation
            move_evals.sort(key=lambda x: x["depth"], reverse=True)
            move_evals = move_evals[0:1]
            for eval in move_evals:
                # Add the evaluations as a comment to the move
                # eval is a dictionary with keys 'pvs', 'knodes', and 'depth'
                # 'pvs' is a list of dictionaries with keys 'cp' and 'line'
                # 'cp' is the centipawn evaluation and 'line' is the best line
                # 'knodes' is the number of nodes searched and 'depth' is the search depth
                # Add the varrious lines as variations
                if "pvs" in eval:
                    # sort the pvs by cp or mate.
                    # cp may be None if mate is certain
                    eval["pvs"].sort(key=lambda x: x.get("mate", x.get("cp", 0)), reverse=True)
                    top_pvs = eval["pvs"]
                    #top_pvs = eval["pvs"][0:max_variations]

                    for pv in top_pvs:
                        # pv is a dictionary with keys 'cp', 'line' and 'mate'
                        # 'cp' is the centipawn evaluation, 'line' is the best line and 'mate' is the mate score
                        # if mate is certain, cp is None 
                        is_first_move = True
                        pv_moves =  pv["line"].split()[0:max_variations_depth]
                        pv_node = node
                        for pv_move in pv_moves:
                            variation_move = chess.Move.from_uci(pv_move)
                            pv_node = pv_node.add_variation(variation_move) 
                            visits = get_visits_from_node(pv_node)
                            if visits > 1:
                                pv_node.comment += f" Visits: {visits}"
                            # If there is a mate value, add it
                            if is_first_move:
                                if "mate" in pv and pv["mate"] is not None:
                                    score = chess.engine.Mate(pv["mate"])
                                    pv_node.comment += f" Mate in {pv['mate']},"
                                else:
                                    score = chess.engine.Cp(pv["cp"])
                                ## Add the evals and move to the node
                                eval_score = chess.engine.PovScore(score, chess.WHITE)
                                pv_node.set_eval(eval_score, depth = eval["depth"])
                                ## Add the evaluation as a comment to the variation
                                pv_node.comment += f" Nodes: {eval['knodes']}, Depth: {eval['depth']}"
                                is_first_move = False
    return node

def append_to_file(output_file_path, content):
    with open(output_file_path, 'a') as output_file:
        output_file.write(content)
def add_evaluation_to_node(node, move_evals, next_move):
    if move_evals:
        if "evals" in move_evals:
            move_evals = move_evals["evals"]
            ## Keeping max/max few depth evaluation
            move_evals.sort(key=lambda x: x["depth"], reverse=True)
            for eval in move_evals:
                if "pvs" in eval:
                    for pv in eval["pvs"]:
                        if pv["line"].split()[0] == next_move:
                            # Add score to the node
                            if "mate" in pv and pv["mate"] is not None:
                                score = chess.engine.Mate(pv["mate"])
                            else:
                                score = chess.engine.Cp(pv["cp"])
                            node.set_eval(chess.engine.PovScore(score, chess.WHITE), depth = eval["depth"])
                            return node
    return node


def annotate_pgn(pgn_file_path, evaluation_file_path, output_file_path):
    global pgn_positions
    ## Delete output file first
    if Path(output_file_path).is_file():
        os.remove(output_file_path)

    pgn_positions = generate_fens_from_pgn(pgn_file_path)
    evals = load_evaluations(evaluation_file_path, pgn_positions)
    print (f"Total positions found in evaluations: {len(evals)}")
    # Example of evals:
    # {
       # {'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -': {'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -', 'evals': [{'pvs': [{'cp': 18, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}], 'knodes': 105848192, 'depth': 70}, {'pvs': [{'cp': 15, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}, {'cp': 18, 'line': 'c7c5 b1c3 d7d6 g1f3 a7a6 d2d4 c5d4 f3d4 g8f6 f1e2'}, {'cp': 20, 'line': 'c7c6 d2d4 d7d5 e4e5 c8f5 c2c3 e7e6 f1e2 c6c5 g1f3'}, {'cp': 35, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}], 'knodes': 144730007, 'depth': 60}, {'pvs': [{'cp': 18, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}, {'cp': 24, 'line': 'c7c6 b1c3 d7d5 d2d4 d5e4 c3e4 c8f5 e4g3 f5g6 g1f3'}, {'cp': 32, 'line': 'c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 d7d6 c1g5'}, {'cp': 32, 'line': 'e7e6 d2d4 d7d5 b1c3 d5e4 c3e4 b8d7 g1f3 g8f6 e4f6'}, {'cp': 36, 'line': 'b8c6 d2d4 d7d5 e4e5 f7f6 f2f4 c8f5 g1f3 e7e6 c2c3'}], 'knodes': 49167055, 'depth': 56}, {'pvs': [{'cp': 20, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}, {'cp': 24, 'line': 'c7c6 d2d4 d7d5 e4e5 c6c5 g1f3 c5d4 d1d4 b8c6 d4f4'}, {'cp': 24, 'line': 'c7c6 d2d4 d7d5 e4e5 c6c5 g1f3 c5d4 d1d4 b8c6 d4f4'}, {'cp': 37, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}, {'cp': 37, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}, {'cp': 39, 'line': 'b8c6 d2d4 d7d5 e4e5 c8f5 c2c3 e7e6 b1d2 f7f6 f2f4'}, {'cp': 39, 'line': 'b8c6 d2d4 d7d5 e4e5 c8f5 c2c3 e7e6 b1d2 f7f6 f2f4'}], 'knodes': 74689, 'depth': 27}, {'pvs': [{'cp': 16, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}, {'cp': 29, 'line': 'c7c6 d2d4 d7d5 e4e5 c6c5 g1f3 c5d4 d1d4 b8c6 d4f4'}, {'cp': 29, 'line': 'c7c6 d2d4 d7d5 e4e5 c6c5 g1f3 c5d4 d1d4 b8c6 d4f4'}, {'cp': 34, 'line': 'c7c5 g1f3 d7d6 d2d4 g8f6 b1c3 c5d4 f3d4 a7a6 c1e3'}, {'cp': 34, 'line': 'b8c6 d2d4 d7d5 e4e5 c8f5 f1e2 f7f6 f2f4 e7e6 c2c3'}, {'cp': 34, 'line': 'c7c5 g1f3 d7d6 d2d4 g8f6 b1c3 c5d4 f3d4 a7a6 c1e3'}, {'cp': 34, 'line': 'b8c6 d2d4 d7d5 e4e5 c8f5 f1e2 f7f6 f2f4 e7e6 c2c3'}, {'cp': 35, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}, {'cp': 35, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}], 'knodes': 72286, 'depth': 26}, {'pvs': [{'cp': 25, 'line': 'c7c6 d2d4 d7d5 e4e5 c8f5 h2h4 h7h5 c2c4 e7e6 g1f3'}, {'cp': 27, 'line': 'e7e5 g1f3 b8c6 f1b5 g8f6 e1h1 f6e4 f1e1 e4d6 f3e5'}, {'cp': 36, 'line': 'e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3'}, {'cp': 39, 'line': 'c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 g7g6 d4c6'}, {'cp': 41, 'line': 'b8c6 d2d4 d7d5 e4e5 c8f5 c2c3 e7e6 f1e2 f7f6 f2f4'}, {'cp': 48, 'line': 'a7a6 d2d4 e7e6 f1d3 d7d5 b1c3 c7c5 d4c5 f8c5 e4d5'}, {'cp': 53, 'line': 'd7d5 e4d5 d8d5 b1c3 d5d6 d2d4 g8f6 g1f3 g7g6 f1c4'}, {'cp': 55, 'line': 'd7d6 d2d4 g8f6 b1c3 e7e5 g1f3 b8c6 d4d5 c6e7 c1g5'}, {'cp': 55, 'line': 'g8f6 e4e5 f6d5 c2c4 d5b6 d2d4 d7d6 e5d6 e7d6 b1c3'}, {'cp': 57, 'line': 'g7g6 d2d4 f8g7 g1f3 d7d6 b1c3 g8f6 c1e3 e8h8 d1d2'}, {'cp': 65, 'line': 'a7a5 d2d4 e7e6 f1d3 d7d5 b1c3 a5a4 g1f3 a4a3 e1h1'}, {'cp': 67, 'line': 'h7h6 d2d4 e7e6 f1d3 d7d5 b1c3 d5e4 c3e4 g8f6 g1f3'}, {'cp': 80, 'line': 'b7b6 d2d4 e7e6 g1f3 c8b7 f1d3 d7d5 e4d5 d8d5 c2c4'}, {'cp': 88, 'line': 'b8a6 b1c3 e7e6 d2d4 d7d5 e4d5 e6d5 f1a6 b7a6 d1e2'}, {'cp': 91, 'line': 'h7h5 d2d4 e7e6 g1f3 d7d5 b1c3 g8f6 e4e5 f6e4 c3e4'}, {'cp': 107, 'line': 'g8h6 d2d4 c7c6 c1f4 d7d5 b1c3 d5e4 c3e4 h6f5 g1f3'}, {'cp': 113, 'line': 'f7f6 d2d4 e7e6 b1c3 f8b4 d1h5 g7g6 h5h4 f6f5 c1g5'}, {'cp': 129, 'line': 'f7f5 e4f5 g8f6 d2d4 d7d5 f1d3 c7c5 c2c3 e7e6 f5e6'}, {'cp': 145, 'line': 'b7b5 f1b5 c8b7 d2d3 g7g6 g1f3 f8g7 e1h1 g8f6 e4e5'}, {'cp': 157, 'line': 'g7g5 b1c3 d7d6 d2d4 h7h6 h2h4 g5h4 g1f3 a7a6 c1e3'}], 'knodes': 184124, 'depth': 23}]}}
    #}

    # Array of all new pgn that will contain the evaluations
    games_annoted = 0
    with open(pgn_file_path, 'r') as pgn_file:
        while (game := chess.pgn.read_game(pgn_file)) is not None:
            board = game.board()
            # Create a new game to store the annotated moves
            annotated_game = chess.pgn.Game()
            # Add all the headers
            annotated_game.headers = game.headers

            # Start with an empty board for each game
            # create the list of evaluations for the game
            node = annotated_game
            fen  = board.fen()
            fen = fen_modify(fen)
            # Add number of times the position is repeated
            move_evals =  evals.get(fen, None)
            moves_array = []
            ## add moves to moves_array
            for move in game.mainline_moves():
                moves_array.append(move.uci())
            try:
                next_move =  moves_array.pop(0)
            except:
                next_move = None
            node = add_variations_to_node(node, move_evals)
            for move in game.mainline_moves():
                # Generate FEN and modify the last two parts (half-move clock and full move number)

                board.push(move)
                fen = board.fen() # Or just pass True?
                fen = fen_modify(fen)
                move_evals =  evals.get(fen, None)
                visits = get_visits_from_node(node)
                if visits > 1:
                    node.comment += f" Visits: {visits}"
                node = node.add_main_variation(move)
                try:
                    next_move = moves_array.pop(0)
                except:
                    next_move = None
                node = add_variations_to_node(node, move_evals)
                node = add_evaluation_to_node(node, move_evals, next_move)
            # write to the end of file output_file
            content = str(annotated_game) + "\n\n"
            append_to_file(output_file_path, content)
            games_annoted += 1

            # Print progress
            if games_annoted % 1000 == 0:
                print(f"Annotated {games_annoted} games so far")
            if debug and games_annoted > 10:
                print(f"Debug Early Return")
                return



# Paths to input and output files
pgn_file_path = "games.pgn"
evaluation_file_path = "lichess_db_eval.jsonl"
output_file_path = "annotated_games.pgn"
if debug:
    output_file_path = "annotated_games_debug.pgn"

annotate_pgn(pgn_file_path, evaluation_file_path, output_file_path)

