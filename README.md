I have liked the arrows on chessx so I coded this - it basically uses lichess's lichess_db_eval.jsonl file and add following stuff to your pgn file:

1. Evals
2. Variations and Their Evals
3. Number of times it has been played in pgn.

It removes other information - I might in future change it to keep those information intact but at the time - this is what it is!
At the moment, most files I have is raw pgns and it goes pretty well with it.

# Preparation

1. Download lichess_db_eval.jsonl.zst
2. Extract in same directory.

# Usage

1. Save your pgn as games.pgn
2. Run ./run.sh
3. Check annotated_games.pgn after some time. I added progress so be patient.

# How to test?

It doesn't change original file so you can run it without being scared.

To reduce size of pgn to 100/200 games I used this:

```
# Somes games are separated with \n in header some with \n\n 
awk -v RS="\n\n" -v ORS="\n\n" 'NR <= 200' games.pgn > 200.pgn
```

You can run ./debug.pgn command - it basically reduces the traverse and return quickly. Good for testing.

# Disclosures

1. I am not a chess player I know the rules.
2. I am not a python developer, I know the rules. :)

# Give back

1. Consider donating to https://lichess.org/
