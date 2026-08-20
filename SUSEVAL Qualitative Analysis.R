library(tidyverse) 
library(psych)      
library(rstatix)    
library(ggpubr)     
library(effectsize)  
library(lavaan)       
library(knitr)       

set.seed(2026)  # reproducibility for the simulated data

## Section 1: SIMULATE DATA 

n_per_group <- 25   # just based on our target of around 20-30 participants
groups       <- c("Oral_English", "Written_Afrikaans", "Written_Xhosa")
proficiency_5_levels <- c("None", "Basic", "Conversational", "Fluent", "First language")

participants <- tibble(
  participant_id = paste0("P", sprintf("%03d", 1:(n_per_group * length(groups)))),
  group = rep(groups, each = n_per_group),
  proficiency_5 = sample(proficiency_5_levels, n_per_group * length(groups),
                         replace = TRUE, prob = c(0.05, 0.20, 0.35, 0.25, 0.15))
) %>%
  mutate(
    proficiency = case_when(
      proficiency_5 %in% c("None", "Basic") ~ "Low",
      proficiency_5 == "Conversational" ~ "Medium",
      proficiency_5 %in% c("Fluent", "First language") ~ "High"
    ),
    proficiency = factor(proficiency, levels = c("Low", "Medium", "High")),
    first_language = case_when(
      group == "Written_Afrikaans" ~ "Afrikaans",
      group == "Written_Xhosa" ~ "isiXhosa",
      TRUE ~ "English"
    )
  )

cat("\nFull proficiency distribution (5-category):\n")
print(participants %>% count(proficiency_5))
cat("\nSummarized Proficiency distribution (used for statistical tests):\n")
print(participants %>% count(proficiency))

simulate_sus_items <- function(n, mean_score = 70, target_reliability = 0.85) {
  target_prop <- mean_score / 100
  base_logit  <- qlogis(pmin(pmax(target_prop, 0.02), 0.98))
  
  theta <- rnorm(n, mean = base_logit, sd = 1.0)
  item_noise_sd <- sqrt((1 - target_reliability) / target_reliability)
  
  items <- matrix(NA_integer_, nrow = n, ncol = 10)
  for (i in 1:10) {
    p_i <- plogis(theta + rnorm(n, 0, item_noise_sd))
    if (i %% 2 == 1) {
      items[, i] <- rbinom(n, 4, p_i) + 1
    } else {
      items[, i] <- rbinom(n, 4, 1 - p_i) + 1
    }
  }
  colnames(items) <- paste0("Q", 1:10)
  as_tibble(items)
}

# Phase 1: Written English mean depends on proficiency

phase1_mean <- participants %>%
  mutate(mean_score = case_when(
    proficiency == "High"   ~ 78,
    proficiency == "Medium" ~ 70,
    proficiency == "Low"    ~ 60
  )) %>% pull(mean_score)

phase1_items <- map_dfr(phase1_mean, ~ simulate_sus_items(1, .x))
names(phase1_items) <- paste0("P1_", names(phase1_items))

# Phase 2: depends on group AND proficiency 
# given a small boost for demo data just to make results more interesting

phase2_boost <- participants %>%
  mutate(boost = case_when(
    group == "Oral_English"      & proficiency == "Low"    ~ 12,
    group == "Oral_English"      & proficiency == "Medium" ~ 6,
    group == "Oral_English"      & proficiency == "High"   ~ 2,
    group == "Written_Afrikaans" & proficiency == "Low"    ~ 15,
    group == "Written_Afrikaans" & proficiency == "Medium" ~ 8,
    group == "Written_Afrikaans" & proficiency == "High"   ~ 3,
    group == "Written_Xhosa"     & proficiency == "Low"    ~ 15,
    group == "Written_Xhosa"     & proficiency == "Medium" ~ 8,
    group == "Written_Xhosa"     & proficiency == "High"   ~ 3
  )) %>% pull(boost)

phase2_mean <- phase1_mean + phase2_boost
phase2_items <- map_dfr(phase2_mean, ~ simulate_sus_items(1, .x))
names(phase2_items) <- paste0("P2_", names(phase2_items))

raw_data <- bind_cols(participants, phase1_items, phase2_items)

# Delete Section 1 for real data
# raw_data <- read_csv("your_sus_data.csv")
# Required columns: participant_id, group, proficiency, first_language, P1_Q1...P1_Q10 (Phase 1 items), P2_Q1...P2_Q10 (Phase 2 items)

glimpse(raw_data)


## Section 2: SUS SCORING

score_sus_phase <- function(df, prefix) {
  odd_cols  <- paste0(prefix, "_Q", seq(1, 9, 2))
  even_cols <- paste0(prefix, "_Q", seq(2, 10, 2))
  df %>%
    mutate(
      across(all_of(odd_cols),  ~ . - 1, .names = "s_{.col}"),
      across(all_of(even_cols), ~ 5 - ., .names = "s_{.col}")
    ) %>%
    rowwise() %>%
    mutate("{prefix}_SUS" := sum(c_across(starts_with(paste0("s_", prefix)))) * 2.5) %>%
    ungroup() %>%
    select(-starts_with(paste0("s_", prefix)))
}

scored_data <- raw_data %>%
  score_sus_phase("P1") %>%
  score_sus_phase("P2") %>%
  mutate(SUS_diff = P2_SUS - P1_SUS)   # positive = Phase 2 rated higher than Phase 1

cat("\nScored data preview:\n")
print(scored_data %>% select(participant_id, group, proficiency, P1_SUS, P2_SUS, SUS_diff) %>% head())

# Section 3: RELIABILITY — Cronbach's alpha per SUS VERSION
# Requires alpha >= 0.7 as evidence each version is internally consistent before trusting any score comparisons.

alpha_for_version <- function(df, prefix) {
  items <- df %>% select(starts_with(paste0(prefix, "_Q")))
  names(items) <- gsub(paste0(prefix, "_"), "", names(items))
  items_rc <- items
  items_rc[paste0("Q", seq(2, 10, 2))] <- 5 - items[paste0("Q", seq(2, 10, 2))]
  a <- psych::alpha(items_rc, warnings = FALSE)
  round(a$total$raw_alpha, 3)
}

reliability_table <- tibble(
  version = c("Written English (all)", "Oral English",
              "Written Afrikaans", "Written isiXhosa"),
  cronbach_alpha = c(
    alpha_for_version(scored_data, "P1"),
    alpha_for_version(filter(scored_data, group == "Oral_English"), "P2"),
    alpha_for_version(filter(scored_data, group == "Written_Afrikaans"), "P2"),
    alpha_for_version(filter(scored_data, group == "Written_Xhosa"), "P2")
  ),
  n = c(nrow(scored_data),
        sum(scored_data$group == "Oral_English"),
        sum(scored_data$group == "Written_Afrikaans"),
        sum(scored_data$group == "Written_Xhosa")),
  meets_threshold_0.7 = cronbach_alpha >= 0.7
)

cat("\nReliability (Cronbach's Alpha) by SUS Version \n")
print(reliability_table)

# Section 4: CONSTRUCT VALIDITY — Confirmatory Factor Analysis (per version)
# Tests whether each translated version preserves SUS's unidimensional factor structure

run_cfa <- function(df, prefix, label) {
  items <- df %>% select(starts_with(paste0(prefix, "_Q")))
  names(items) <- gsub(paste0(prefix, "_"), "", names(items))
  items[paste0("Q", seq(2, 10, 2))] <- 5 - items[paste0("Q", seq(2, 10, 2))] # for negative items
  
  model <- "SUS =~ Q1+Q2+Q3+Q4+Q5+Q6+Q7+Q8+Q9+Q10"
  fit <- tryCatch(cfa(model, data = items), error = function(e) NULL)
  
  converged <- !is.null(fit) && isTRUE(tryCatch(lavInspect(fit, "converged"), error = function(e) FALSE))
  if (!converged) {
    cat("  [", label, "] CFA did not converge cleanly - returning NA\n")
    return(tibble(version = label, cfi = NA, rmsea = NA, srmr = NA))
  }
  
  fm <- tryCatch(fitMeasures(fit, c("cfi", "rmsea", "srmr")),
                 error = function(e) c(cfi = NA, rmsea = NA, srmr = NA))
  tibble(version = label, cfi = round(fm["cfi"],3),
         rmsea = round(fm["rmsea"],3), srmr = round(fm["srmr"],3))
}

cfa_results <- bind_rows(
  run_cfa(scored_data, "P1", "Written English"),
  run_cfa(filter(scored_data, group == "Oral_English"), "P2", "Oral English"),
  run_cfa(filter(scored_data, group == "Written_Afrikaans"), "P2", "Written Afrikaans"),
  run_cfa(filter(scored_data, group == "Written_Xhosa"), "P2", "Written isiXhosa")
)

cat("\nCFA Fit Indices by Version (CFI>.90, RMSEA<.08, SRMR<.08 = acceptable)\n")
print(cfa_results)

# Section 5: DESCRIPTIVE STATISTICS — Phase 1 vs Phase 2, by group

descriptives <- scored_data %>%
  group_by(group) %>%
  summarise(
    n = n(),
    Phase1_mean = round(mean(P1_SUS), 2), Phase1_sd = round(sd(P1_SUS), 2),
    Phase2_mean = round(mean(P2_SUS), 2), Phase2_sd = round(sd(P2_SUS), 2),
    Mean_diff   = round(mean(SUS_diff), 2), diff_sd = round(sd(SUS_diff), 2),
    .groups = "drop"
  )

cat("\nDescriptives: Phase 1 (Written English) vs Phase 2, by group\n")
print(descriptives)

# Section 6: HYPOTHESIS TESTS
# Each comparison is within the same participants (Phase 1 vs Phase 2)
# Wilcoxon used since a few outliers can skew the t test. (does not assume normality)

run_paired_comparison <- function(df, group_name, hypothesis_label) {
  d <- df %>% filter(group == group_name)
  
  norm_check <- shapiro.test(d$SUS_diff)
  
  t_res <- t.test(d$P2_SUS, d$P1_SUS, paired = TRUE)
  w_res <- wilcox.test(d$P2_SUS, d$P1_SUS, paired = TRUE) # robustness check since small sample size (around 25)
  d_effect <- effectsize::cohens_d(d$P2_SUS, d$P1_SUS, paired = TRUE) 
  
  cat("\n", hypothesis_label, "\n")
  cat("Group:", group_name, "| n =", nrow(d), "\n")
  cat("Shapiro-Wilk on difference scores: W =", round(norm_check$statistic,3),
      ", p =", round(norm_check$p.value,3),
      ifelse(norm_check$p.value < .05, " (non-normal -> lean on Wilcoxon)",
             " (normal -> paired t-test OK)"), "\n")
  cat("Paired t-test:  t(", t_res$parameter, ") =", round(t_res$statistic,3),
      ", p =", format.pval(t_res$p.value, digits=3),
      ", mean diff =", round(t_res$estimate,2), "\n")
  cat("Wilcoxon signed-rank: V =", w_res$statistic,
      ", p =", format.pval(w_res$p.value, digits=3), "\n")
  cat("Effect size (Cohen's d, paired):", round(d_effect$Cohens_d,3),
      " [", round(d_effect$CI_low,3), ",", round(d_effect$CI_high,3), "]\n")
  
  tibble(
    hypothesis = hypothesis_label, group = group_name, n = nrow(d),
    mean_diff = round(t_res$estimate,2),
    t_stat = round(t_res$statistic,3), t_p = t_res$p.value,
    wilcoxon_p = w_res$p.value, cohens_d = round(d_effect$Cohens_d,3)
  )
}

h2_result  <- run_paired_comparison(scored_data, "Oral_English",
                                    "H2: Written English vs Oral English (mode effect)")
h1a_result <- run_paired_comparison(scored_data, "Written_Afrikaans",
                                    "H1a: Written English vs Written Afrikaans (localisation)")
h1b_result <- run_paired_comparison(scored_data, "Written_Xhosa",
                                    "H1b: Written English vs Written isiXhosa (localisation)")

hypothesis_summary <- bind_rows(h2_result, h1a_result, h1b_result)
cat("\nSummary: Paired Comparison Results (H1 & H2) \n")
print(hypothesis_summary)

# Section 7. H3 — PROFICIENCY AS A MODERATOR OF THE PHASE1->PHASE2 CHANGE
# Tests whether the size of the Phase1 to Phase2 shift depends on self-reported English proficiency
# Kruskal-Wallis is used since small sample size and doesn't need normality assumption like ANOVA

cat("\nDescriptive: Full 5-category proficiency breakdown, by group\n")
print(scored_data %>% count(group, proficiency_5) %>% arrange(group, proficiency_5))

test_proficiency_moderation <- function(df, group_name) {
  d <- df %>% filter(group == group_name)
  kw <- kruskal.test(SUS_diff ~ proficiency, data = d)
  eff <- d %>% kruskal_effsize(SUS_diff ~ proficiency)
  
  cat("\nProficiency moderation:", group_name, "\n")
  cat("Kruskal-Wallis: chi-sq =", round(kw$statistic,3), ", df =", kw$parameter,
      ", p =", format.pval(kw$p.value, digits=3), "\n")
  print(d %>% group_by(proficiency) %>%
          summarise(n=n(), mean_diff=round(mean(SUS_diff),2), sd=round(sd(SUS_diff),2), .groups="drop"))
  
  tibble(group = group_name, chi_sq = round(kw$statistic,3), p = kw$p.value,
         epsilon_sq = round(eff$effsize, 3))
}

h3_results <- bind_rows(
  test_proficiency_moderation(scored_data, "Oral_English"),
  test_proficiency_moderation(scored_data, "Written_Afrikaans"),
  test_proficiency_moderation(scored_data, "Written_Xhosa")
)

cat("\nSummary: H3 Proficiency Moderation Results\n")
print(h3_results)

## Section 8: PLOTS
theme_set(theme_minimal(base_size = 13))

## 8a. Paired plot
plot_data <- scored_data %>%
  select(participant_id, group, proficiency, P1_SUS, P2_SUS) %>%
  pivot_longer(cols = c(P1_SUS, P2_SUS), names_to = "phase", values_to = "SUS_score") %>%
  mutate(phase = recode(phase, P1_SUS = "Phase 1\n(Written English)", P2_SUS = "Phase 2"))

p1 <- ggplot(plot_data, aes(x = phase, y = SUS_score, group = participant_id, color = proficiency)) +
  geom_line(alpha = 0.4) +
  geom_point(alpha = 0.6) +
  facet_wrap(~ group) +
  labs(title = "Within-Subjects Change: Phase 1 -> Phase 2 SUS Score",
       subtitle = "Each line = one participant. Faceted by Phase 2 condition.",
       x = NULL, y = "SUS Score (0-100)", color = "English\nProficiency") +
  theme(legend.position = "bottom")
print(p1)
ggsave("sus_paired_change_by_group.png", p1, width = 10, height = 5, dpi = 300)

## 8b. Reliability bar chart across the four versions
p2 <- ggplot(reliability_table, aes(x = version, y = cronbach_alpha, fill = meets_threshold_0.7)) +
  geom_col() +
  geom_hline(yintercept = 0.7, linetype = "dashed", color = "black") +
  scale_fill_manual(values = c("TRUE" = "#4CAF50", "FALSE" = "#E57373"), guide = "none") +
  labs(title = "Internal Consistency (Cronbach's Alpha) by SUS Version",
       subtitle = "Dashed line = 0.70 acceptability threshold",
       x = NULL, y = "Cronbach's Alpha") +
  theme(axis.text.x = element_text(angle = 20, hjust = 1))
print(p2)
ggsave("sus_reliability_by_version.png", p2, width = 8, height = 5, dpi = 300)

## 8c. Distribution of Phase1-> Phase2 difference scores by proficiency
p3 <- ggplot(scored_data, aes(x = proficiency, y = SUS_diff, fill = proficiency)) +
  geom_boxplot(alpha = 0.7) +
  geom_jitter(width = 0.15, alpha = 0.4) +
  geom_hline(yintercept = 0, linetype = "dashed") +
  facet_wrap(~ group) +
  labs(title = "Phase 1 -> Phase 2 Score Change by English Proficiency",
       subtitle = "Positive = Phase 2 rated higher than Phase 1 Written English",
       x = "Self-Reported English Proficiency", y = "SUS Score Change") +
  theme(legend.position = "none")
print(p3)
ggsave("sus_proficiency_moderation.png", p3, width = 10, height = 5, dpi = 300)

## 9. EXPORT SUMMARY TABLES 
write_csv(scored_data, "sus_scored_data_participant_level.csv")
write_csv(reliability_table, "sus_reliability_by_version.csv")
write_csv(cfa_results, "sus_cfa_fit_by_version.csv")
write_csv(descriptives, "sus_descriptives_by_group.csv")
write_csv(hypothesis_summary, "sus_H1_H2_paired_test_results.csv")
write_csv(h3_results, "sus_H3_proficiency_moderation_results.csv")
write_csv(scored_data %>% count(group, proficiency_5), "sus_proficiency_5cat_breakdown.csv")
