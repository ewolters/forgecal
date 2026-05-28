#!/usr/bin/env Rscript
# cal_spc.R — Generate golden SPC reference values using R's qcc package.
#
# R's qcc is THE reference for SPC: Cp/Cpk, control charts, Nelson rules.
# These values are what forgespc must match.

if (!exists("write_golden")) source(file.path(.forgecal_r_dir, "helpers.R"))
suppressPackageStartupMessages(library(qcc))

outfile <- file.path(.forgecal_root, "golden", "spc", "r_reference.json")
cases <- list()

# Helper: run qcc without plotting (qcc 2.7 doesn't support plot=FALSE)
run_qcc <- function(...) {
  invisible(capture.output(q <- qcc(...)))
  q
}
run_pc <- function(...) {
  invisible(capture.output(pc <- process.capability(...)))
  pc
}

# ── CAL-R-SPC-001: I-MR chart on N(50,2) data ──
set.seed(42)
imr_data <- rnorm(30, mean = 50, sd = 2)

q_i <- run_qcc(imr_data, type = "xbar.one")
mr <- abs(diff(imr_data))
mr_bar <- mean(mr)
sigma_est <- q_i$std.dev

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-001",
  description = "I-MR chart: N(50,2) n=30, sigma from MR/d2",
  package = "forgespc", category = "imr",
  data = list(values = imr_data),
  expectations = list(
    expect_numeric("center", q_i$center, 0.01),
    expect_numeric("sigma", sigma_est, 0.01),
    expect_numeric("ucl", q_i$limits[2], 0.01),
    expect_numeric("lcl", q_i$limits[1], 0.01),
    expect_numeric("mr_bar", mr_bar, 0.01)
  )
)

# ── CAL-R-SPC-002: X-bar/R chart, subgroups of 5 ──
set.seed(123)
xbar_data <- matrix(rnorm(100, mean = 25, sd = 1), ncol = 5)

q_xbar <- run_qcc(xbar_data, type = "xbar")
q_r    <- run_qcc(xbar_data, type = "R")

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-002",
  description = "X-bar/R chart: N(25,1) 20 subgroups of 5",
  package = "forgespc", category = "xbar_r",
  data = list(subgroups = as.list(as.data.frame(t(xbar_data)))),
  config = list(subgroup_size = 5),
  expectations = list(
    expect_numeric("xbar_center", q_xbar$center, 0.01),
    expect_numeric("xbar_ucl", q_xbar$limits[2], 0.01),
    expect_numeric("xbar_lcl", q_xbar$limits[1], 0.01),
    expect_numeric("r_bar", q_r$center, 0.01),
    expect_numeric("r_ucl", q_r$limits[2], 0.01),
    expect_numeric("sigma", q_xbar$std.dev, 0.01)
  )
)

# ── CAL-R-SPC-003: Process capability on N(50,2) ──
set.seed(42)
cap_data <- rnorm(100, mean = 50, sd = 2)
lsl <- 40; usl <- 60

q_cap <- run_qcc(cap_data, type = "xbar.one")
pc <- run_pc(q_cap, spec.limits = c(lsl, usl))

# qcc 2.7 uses Cp, Cp_l, Cp_u, Cp_k; column = "Value"
cp_val  <- pc$indices["Cp",   "Value"]
cpk_val <- pc$indices["Cp_k", "Value"]
cpl_val <- pc$indices["Cp_l", "Value"]
cpu_val <- pc$indices["Cp_u", "Value"]
sigma_level <- 3 * cpk_val + 1.5

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-003",
  description = "Capability: N(50,2) LSL=40 USL=60",
  package = "forgespc", category = "capability",
  data = list(values = cap_data),
  config = list(lsl = lsl, usl = usl),
  expectations = list(
    expect_numeric("cp",  cp_val, 0.02),
    expect_numeric("cpk", cpk_val, 0.02),
    expect_numeric("cpl", cpl_val, 0.02),
    expect_numeric("cpu", cpu_val, 0.02),
    expect_numeric("sigma_level", sigma_level, 0.1),
    expect_gt("cp", 1.0),
    expect_gt("cpk", 1.0)
  )
)

# ── CAL-R-SPC-004: p-chart ──
set.seed(99)
n_samples <- 20
sample_sizes <- rep(100, n_samples)
defectives <- rbinom(n_samples, 100, 0.05)

q_p <- run_qcc(defectives, type = "p", sizes = sample_sizes)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-004",
  description = "p-chart: 20 samples of 100, p~0.05",
  package = "forgespc", category = "p_chart",
  data = list(defectives = defectives, sample_sizes = sample_sizes),
  expectations = list(
    expect_numeric("p_bar", q_p$center, 0.005),
    expect_numeric("ucl", q_p$limits[1, "UCL"], 0.005),
    expect_numeric("lcl", max(0, q_p$limits[1, "LCL"]), 0.005)
  )
)

# ── CAL-R-SPC-005: c-chart ──
set.seed(77)
defect_counts <- rpois(25, lambda = 8)
q_c <- run_qcc(defect_counts, type = "c")

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-005",
  description = "c-chart: 25 samples, lambda~8 defects/unit",
  package = "forgespc", category = "c_chart",
  data = list(defect_counts = defect_counts),
  expectations = list(
    expect_numeric("c_bar", q_c$center, 0.01),
    expect_numeric("ucl", q_c$limits[1, "UCL"], 0.1),
    expect_numeric("lcl", max(0, q_c$limits[1, "LCL"]), 0.1)
  )
)

# ── CAL-R-SPC-006: Capability on centered process ──
set.seed(200)
centered <- rnorm(200, mean = 100, sd = 0.5)
q_cen <- run_qcc(centered, type = "xbar.one")
pc2 <- run_pc(q_cen, spec.limits = c(97, 103))

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-SPC-006",
  description = "Capability: well-centered N(100,0.5) LSL=97 USL=103",
  package = "forgespc", category = "capability",
  data = list(values = centered),
  config = list(lsl = 97, usl = 103),
  expectations = list(
    expect_numeric("cp",  pc2$indices["Cp",   "Value"], 0.05),
    expect_numeric("cpk", pc2$indices["Cp_k", "Value"], 0.05),
    expect_gt("cp", 1.5),
    expect_gt("cpk", 1.5)
  )
)

write_golden(cases, outfile)
cat("SPC calibration: done\n")
