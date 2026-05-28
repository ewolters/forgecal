#!/usr/bin/env Rscript
# cal_stat.R — Generate golden statistical reference values using base R.
#
# base R's t.test, aov, cor.test, chisq.test are the reference implementations.

if (!exists("write_golden")) source(file.path(.forgecal_r_dir, "helpers.R"))

outfile <- file.path(.forgecal_root, "golden", "stat", "r_reference.json")
cases <- list()

# ── CAL-R-STAT-001: One-sample t-test ──
x <- c(10, 12, 11, 13, 14, 12, 11, 10, 15, 13)
tt <- t.test(x, mu = 0)
d <- mean(x) / sd(x)  # Cohen's d

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-001",
  description = "One-sample t-test: 10 values, μ₀=0",
  package = "forgestat", category = "ttest_one_sample",
  data = list(data = x),
  config = list(mu = 0),
  expectations = list(
    expect_numeric("t_statistic", as.numeric(tt$statistic), 0.001),
    expect_numeric("p_value", tt$p.value, 0.0001),
    expect_numeric("cohens_d", d, 0.01),
    expect_numeric("df", as.numeric(tt$parameter), 0.001),
    expect_numeric("mean", mean(x), 0.001),
    expect_lt("p_value", 0.001)
  )
)

# ── CAL-R-STAT-002: Two-sample Welch t-test ──
x1 <- c(10, 12, 11, 13, 14, 15, 12, 11)
x2 <- c(20, 22, 21, 23, 24, 25, 22, 21)
tt2 <- t.test(x1, x2)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-002",
  description = "Two-sample Welch t-test: 10-unit gap",
  package = "forgestat", category = "ttest_two_sample",
  data = list(x1 = x1, x2 = x2),
  expectations = list(
    expect_numeric("t_statistic", as.numeric(tt2$statistic), 0.001),
    expect_numeric("p_value", tt2$p.value, 0.0001),
    expect_numeric("df", as.numeric(tt2$parameter), 0.01),
    expect_lt("p_value", 0.001)
  )
)

# ── CAL-R-STAT-003: Paired t-test ──
# Differences need some variance (constant differences crash t.test)
pre  <- c(10, 12, 11, 13, 14, 15, 12, 11, 10, 13)
post <- c(12.1, 13.8, 13.2, 15.0, 16.3, 16.7, 14.1, 13.4, 11.8, 15.2)
tt3 <- t.test(pre, post, paired = TRUE)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-003",
  description = "Paired t-test: consistent +2 shift",
  package = "forgestat", category = "ttest_paired",
  data = list(x1 = pre, x2 = post),
  expectations = list(
    expect_numeric("t_statistic", as.numeric(tt3$statistic), 0.001),
    expect_numeric("p_value", tt3$p.value, 0.0001),
    expect_numeric("mean_diff", as.numeric(tt3$estimate), 0.001),
    expect_lt("p_value", 0.05)
  )
)

# ── CAL-R-STAT-004: One-way ANOVA ──
low  <- c(10, 12, 11, 13, 14)
med  <- c(20, 22, 21, 23, 24)
high <- c(30, 32, 31, 33, 34)
df_aov <- data.frame(
  y = c(low, med, high),
  group = factor(rep(c("Low", "Med", "High"), each = 5))
)
fit <- aov(y ~ group, data = df_aov)
ss <- summary(fit)[[1]]
eta_sq <- ss$`Sum Sq`[1] / sum(ss$`Sum Sq`)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-004",
  description = "One-way ANOVA: 3 groups, 10-unit gaps",
  package = "forgestat", category = "anova_one_way",
  data = list(low = low, med = med, high = high),
  expectations = list(
    expect_numeric("f_statistic", ss$`F value`[1], 0.01),
    expect_numeric("p_value", ss$`Pr(>F)`[1], 0.0001),
    expect_numeric("ss_between", ss$`Sum Sq`[1], 0.01),
    expect_numeric("ss_within", ss$`Sum Sq`[2], 0.01),
    expect_numeric("eta_squared", eta_sq, 0.001),
    expect_gt("eta_squared", 0.9)
  )
)

# ── CAL-R-STAT-005: Pearson correlation ──
x_cor <- c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
y_cor <- c(2.1, 3.9, 6.2, 7.8, 10.1, 12.3, 13.9, 16.0, 18.2, 20.1)
ct <- cor.test(x_cor, y_cor)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-005",
  description = "Pearson correlation: strong linear",
  package = "forgestat", category = "correlation",
  data = list(x = x_cor, y = y_cor),
  expectations = list(
    expect_numeric("r", as.numeric(ct$estimate), 0.0001),
    expect_numeric("p_value", ct$p.value, 0.0001),
    expect_numeric("t_statistic", as.numeric(ct$statistic), 0.001),
    expect_gt("r", 0.99)
  )
)

# ── CAL-R-STAT-006: Chi-square test ──
observed <- matrix(c(50, 30, 20, 40, 60, 50), nrow = 2, byrow = TRUE)
chi <- chisq.test(observed)
cramers_v <- sqrt(chi$statistic / (sum(observed) * (min(dim(observed)) - 1)))

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-006",
  description = "Chi-square test of independence: 2x3",
  package = "forgestat", category = "chi_square",
  data = list(observed = as.list(as.data.frame(observed))),
  expectations = list(
    expect_numeric("chi_sq", as.numeric(chi$statistic), 0.01),
    expect_numeric("p_value", chi$p.value, 0.001),
    expect_numeric("df", as.numeric(chi$parameter), 0.001),
    expect_numeric("cramers_v", as.numeric(cramers_v), 0.01)
  )
)

# ── CAL-R-STAT-007: Mann-Whitney U test ──
a <- c(5, 7, 3, 8, 6)
b <- c(12, 15, 10, 14, 11)
wt <- wilcox.test(a, b, exact = FALSE)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-007",
  description = "Mann-Whitney U: two separated groups",
  package = "forgestat", category = "mann_whitney",
  data = list(a = a, b = b),
  expectations = list(
    expect_numeric("U_statistic", as.numeric(wt$statistic), 0.5),
    expect_numeric("p_value", wt$p.value, 0.005),
    expect_lt("p_value", 0.05)
  )
)

# ── CAL-R-STAT-008: Kruskal-Wallis test ──
g1 <- c(10, 12, 11, 13, 14)
g2 <- c(20, 22, 21, 23, 24)
g3 <- c(30, 32, 31, 33, 34)
kw <- kruskal.test(list(g1, g2, g3))

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-008",
  description = "Kruskal-Wallis: 3 widely separated groups",
  package = "forgestat", category = "kruskal_wallis",
  data = list(g1 = g1, g2 = g2, g3 = g3),
  expectations = list(
    expect_numeric("H_statistic", as.numeric(kw$statistic), 0.01),
    expect_numeric("p_value", kw$p.value, 0.001),
    expect_numeric("df", as.numeric(kw$parameter), 0.001),
    expect_lt("p_value", 0.01)
  )
)

# ── CAL-R-STAT-009: Linear regression ──
x_reg <- 1:20
set.seed(55)
y_reg <- 3 + 2.5 * x_reg + rnorm(20, sd = 1)
fit_lm <- lm(y_reg ~ x_reg)
s <- summary(fit_lm)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-STAT-009",
  description = "Simple linear regression: y = 3 + 2.5x + ε",
  package = "forgestat", category = "regression",
  data = list(x = x_reg, y = y_reg),
  expectations = list(
    expect_numeric("intercept", coef(fit_lm)[1], 0.5),
    expect_numeric("slope", coef(fit_lm)[2], 0.05),
    expect_numeric("r_squared", s$r.squared, 0.001),
    expect_numeric("f_statistic", s$fstatistic[1], 0.1),
    expect_gt("r_squared", 0.95)
  )
)

write_golden(cases, outfile)
cat("STAT calibration: done\n")
