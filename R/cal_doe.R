#!/usr/bin/env Rscript
# cal_doe.R — Generate golden DOE reference values using R's FrF2, rsm, DoE.base.
#
# These packages are the reference for factorial designs, CCD, Box-Behnken.

if (!exists("write_golden")) source(file.path(.forgecal_r_dir, "helpers.R"))
suppressPackageStartupMessages({
  library(FrF2)
  library(rsm)
  library(DoE.base)
})

outfile <- file.path(.forgecal_root, "golden", "doe", "r_reference.json")
cases <- list()

# ── CAL-R-DOE-001: 2^3 full factorial ──
ff <- FrF2(nruns = 8, nfactors = 3, randomize = FALSE)
mat <- as.matrix(ff)
storage.mode(mat) <- "integer"

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-001",
  description = "2^3 full factorial: 8 runs, 3 factors",
  package = "forgedoe", category = "factorial",
  config = list(k = 3, type = "full"),
  data = list(matrix = as.list(as.data.frame(mat))),
  expectations = list(
    expect_equals("n_runs", 8),
    expect_equals("n_factors", 3)
  )
)

# ── CAL-R-DOE-002: 2^(5-1) fractional factorial, Resolution V ──
ff5 <- FrF2(nruns = 16, nfactors = 5, randomize = FALSE)
mat5 <- as.matrix(ff5)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-002",
  description = "2^(5-1) fractional factorial: 16 runs, Res V",
  package = "forgedoe", category = "factorial",
  config = list(k = 5, resolution = 5),
  data = list(matrix = as.list(as.data.frame(mat5))),
  expectations = list(
    expect_equals("n_runs", 16),
    expect_equals("n_factors", 5)
  )
)

# ── CAL-R-DOE-003: CCD for 3 factors ──
ccd3 <- ccd(3, n0 = c(2, 2), randomize = FALSE, inscribed = FALSE)
ccd_mat <- as.matrix(ccd3[, 3:5])  # coded factor columns
n_ccd <- nrow(ccd_mat)
alpha_ccd <- sqrt(3)  # face-centered if alpha=1, rotatable if alpha=sqrt(k)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-003",
  description = "CCD: 3 factors, rotatable",
  package = "forgedoe", category = "response_surface",
  config = list(k = 3, type = "ccd"),
  expectations = list(
    expect_equals("n_factorial", 8),
    expect_equals("n_factors", 3),
    expect_gt("n_runs", 14)
  )
)

# ── CAL-R-DOE-004: Box-Behnken for 3 factors ──
bbd3 <- bbd(3, n0 = 2, randomize = FALSE)
bbd_mat <- as.matrix(bbd3[, 3:5])
n_bbd <- nrow(bbd_mat)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-004",
  description = "Box-Behnken: 3 factors",
  package = "forgedoe", category = "response_surface",
  config = list(k = 3, type = "bbd"),
  expectations = list(
    expect_equals("n_runs", n_bbd),
    expect_equals("n_factors", 3)
  )
)

# ── CAL-R-DOE-005: Plackett-Burman for 7 factors ──
pb <- pb(nruns = 12, nfactors = 7, randomize = FALSE)
pb_mat <- as.matrix(pb)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-005",
  description = "Plackett-Burman: 7 factors, 12 runs",
  package = "forgedoe", category = "screening",
  config = list(k = 7, type = "pb"),
  expectations = list(
    expect_equals("n_runs", 12),
    expect_equals("n_factors", 7)
  )
)

# ── CAL-R-DOE-006: RSM model fit ──
set.seed(300)
x1 <- runif(20, -1, 1)
x2 <- runif(20, -1, 1)
y  <- 10 + 3*x1 - 2*x2 + 1.5*x1*x2 - x1^2 - 0.5*x2^2 + rnorm(20, sd = 0.5)
df_rsm <- data.frame(x1 = x1, x2 = x2, y = y)
fit_rsm <- lm(y ~ x1 + x2 + x1:x2 + I(x1^2) + I(x2^2), data = df_rsm)
s_rsm <- summary(fit_rsm)

cases[[length(cases) + 1]] <- make_case(
  case_id = "CAL-R-DOE-006",
  description = "RSM quadratic fit: y = 10 + 3x1 - 2x2 + 1.5x1x2 - x1² - 0.5x2²",
  package = "forgedoe", category = "analysis",
  data = list(x1 = x1, x2 = x2, y = y),
  expectations = list(
    expect_numeric("intercept", coef(fit_rsm)[1], 0.5),
    expect_numeric("beta_x1", coef(fit_rsm)[2], 0.3),
    expect_numeric("beta_x2", coef(fit_rsm)[3], 0.3),
    expect_numeric("r_squared", s_rsm$r.squared, 0.01),
    expect_gt("r_squared", 0.9)
  )
)

write_golden(cases, outfile)
cat("DOE calibration: done\n")
