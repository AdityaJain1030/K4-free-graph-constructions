# 1. How many graphs total
wc -l r45_24.g6.txt

# 2. Are they all the same size? (g6 encodes N in first bytes, same line length = same N)
awk '{ print length($0) }' r45_24.g6.txt | sort -u

# 3. Analyse just 5 graphs in detail
python r45_analysis.py r45_24.g6.txt --max 5

# 4. Quick alpha/degree check on 100 random samples
shuf -n 100 r45_24.g6.txt > r45_sample.g6
python r45_analysis.py r45_sample.g6 --quiet