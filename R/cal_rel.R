#!/usr/bin/env Rscript
# cal_rel.R — Generate golden reliability reference values using WeibullR + survival.
#
# WeibullR is the R implementation of Abernethy's methods.
# survival is the standard for Kaplan-Meier, Cox PH, survreg.

if (!exists("write_golden")) source(file.path(.forgecal_r_dir, "helpers.R"))
suppressPackageStartupMessages({
  library(WeibullR)
  library(survival)
})

outfile <- file.path(.forgecal_root, "golden", "rel", "r_reference.json")
cases <- list()

# ── CAL-R-REL-001: Weibull MLE (complete data) ──
set.seed(42)
weib_data <- rweibull(50, shape = 2.5, scale = 100)

wfit <- MLEw2p(weib_data)
# MLEw2p returns c(Eta, Beta, LL)
eta_hat  <- wfit[1]
beta_hat <- wfit[2]

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-REL-001",
  description = "Weibull 2P MLE: shape=2.5, scale=100, n=50 complete",
  package = "forgerel", category = "weibull",
  data = list(times = weib_data),
  config = list(censored = rep(1, 50)),
  expectations = list(
    expect_numeric("beta", beta_hat, 0.15),
    expect_numeric("eta", eta_hat, 5.0),
    expect_between("beta", 1.5, 4.0),
    expect_between("eta", 70, 140)
  )
)

# ── CAL-R-REL-002: Weibull MLE (right-censored data) ──
set.seed(99)
true_times <- rweibull(30, shape = 1.8, scale = 500)
censor_time <- 400
observed <- pmin(true_times, censor_time)
censored <- as.integer(true_times <= censor_time)  # 1=failed, 0=censored

# survreg parameterization: log(T) = mu + sigma*W, W ~ Gumbel
sfit <- survreg(Surv(observed, censored) ~ 1, dist = "weibull")
# Convert survreg params to shape/scale
beta_sr <- 1 / sfit$scale
eta_sr  <- exp(coef(sfit))

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-REL-002",
  description = "Weibull 2P MLE with right censoring at t=400",
  package = "forgerel", category = "weibull",
  data = list(times = observed, censored = censored),
  config = list(censor_time = censor_time),
  expectations = list(
    expect_numeric("beta", as.numeric(beta_sr), 0.3),
    expect_numeric("eta", as.numeric(eta_sr), 30),
    expect_between("beta", 1.0, 3.5),
    expect_between("eta", 300, 800)
  )
)

# ── CAL-R-REL-003: Kaplan-Meier survival ──
set.seed(10)
km_times  <- c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
km_events <- c(1, 0, 1, 0, 1, 1, 0, 1, 0, 1,  0,  1)  # 1=death, 0=censored
km_fit <- survfit(Surv(km_times, km_events) ~ 1)
# Survival at t=6
s6 <- summary(km_fit, times = 6)$surv
# Median survival
med_surv <- summary(km_fit)$table["median"]

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-REL-003",
  description = "Kaplan-Meier survival curve with censoring",
  package = "forgerel", category = "survival",
  data = list(times = km_times, events = km_events),
  expectations = list(
    expect_numeric("survival_at_6", as.numeric(s6), 0.02),
    expect_between("survival_at_6", 0.3, 0.9)
  )
)

# ── CAL-R-REL-004: MTBF confidence interval (chi-square) ──
# MIL-HDBK-781: failure-truncated test
total_time <- 10000  # total unit-hours
n_failures <- 5
mtbf_point <- total_time / n_failures  # = 2000

# Two-sided 90% CI: lower = 2T / chi2(1-alpha/2, 2r), upper = 2T / chi2(alpha/2, 2r)
alpha <- 0.10
df_lower <- 2 * n_failures
df_upper <- 2 * n_failures
mtbf_lower <- 2 * total_time / qchisq(1 - alpha/2, df_lower)
mtbf_upper <- 2 * total_time / qchisq(alpha/2, df_upper)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-REL-004",
  description = "MTBF chi-square CI: 5 failures in 10000 hrs",
  package = "forgerel", category = "mtbf",
  data = list(total_time = total_time, n_failures = n_failures),
  config = list(confidence = 0.90, test_type = "failure_truncated"),
  expectations = list(
    expect_numeric("mtbf_point", mtbf_point, 1),
    expect_numeric("mtbf_lower", mtbf_lower, 10),
    expect_numeric("mtbf_upper", mtbf_upper, 50),
    expect_gt("mtbf_upper", mtbf_point),
    expect_lt("mtbf_lower", mtbf_point)
  )
)

write_golden(cases, outfile)
cat("REL calibration: done\n")
