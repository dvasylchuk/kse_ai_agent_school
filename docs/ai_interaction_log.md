AI Interaction Log



This log summarises how I used AI as a thinking partner to move from a vague

assignment to a focused, honest analytical project. The point is to show the

reasoning and decisions - not just requests for code.



1\. Narrowing a vague task



I started from a broad brief ("time series analysis of air raid alerts in

Ukraine") and used AI to narrow it deliberately: one region (Kyiv City), one

clear question (temporal clustering), and a small set of simple methods. I

chose scope on purpose rather than trying to analyse every region shallowly.



2\. Correcting my own framing



My first research question assumed its own answer: "Have Kyiv alerts become

more clustered over time?" I recognised this built in a conclusion

(confirmation bias) and reworded it to a neutral version:





"How clustered in time are air raid alerts in Kyiv, and how did the degree of

clustering vary across different periods of the war?"







This neutral framing let the data overturn the tidy "clustering rose over time"

story - which it did.



3\. Auditing data before analysis



Before any analysis I ran a validation step and found real issues, each handled

explicitly:





the actual columns (oblast, raion, hromada, level, started\_at, finished\_at, source);

Kyiv City and Kyivska oblast are separate - I chose the city;

large numbers of exact duplicates - removed transparently, with a full

row-count trail (3,961 raw -> 3,590 in window -> 1,795 after dedup);

a December 2025 granularity change (oblast -> raion level) - I capped the

window at 2025-11-29 to keep recording consistent.





4\. Enforcing strict data discipline



Throughout, I held firm rules and stated them in the code:





no fake, sample, synthetic, or placeholder data;

no assumed column names (the scripts auto-detect and print real names);

fail-loudly loading (stop with a clear reason instead of guessing);

print real computed outputs at every step.





When AI could not run code (no network), it said so plainly rather than

inventing numbers - every result in this project came from running the scripts

locally on the real file.



5\. Keeping methods simple



I resisted over-engineering. The methods are gaps between alerts, a

threshold-based cluster definition (with a 3h/6h/12h sensitivity sweep), and a

rolling burstiness parameter B. I explicitly rejected change point detection

because it would risk causal over-interpretation without better answering the

question.



6\. Reconciling, not cherry-picking




rolling B near zero) looked different at first. Instead of picking the more

dramatic number, I reconciled them: many alerts can be within 6 hours of a

neighbour while the overall spacing is only mildly uneven. Both methods showed

the same non-monotonic year pattern (2022 and 2024 higher; 2023 and 2025

lower), which strengthened the conclusion.



7\. Honest final conclusion



The evidence did not support a simple "clustering increased" narrative, so I

did not claim one. Final conclusion: Kyiv alerts often appeared in short-term

series, but clustering was moderate and varied over time. No causal or

predictive claims were made.
