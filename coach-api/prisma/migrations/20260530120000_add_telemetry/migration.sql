-- CreateTable
CREATE TABLE "SessionTraceEvent" (
    "id" TEXT NOT NULL,
    "schemaVersion" TEXT NOT NULL DEFAULT 'v1',
    "eventId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "ts" BIGINT NOT NULL,
    "source" TEXT NOT NULL,
    "stepId" TEXT,
    "eventType" TEXT NOT NULL,
    "elementKey" TEXT,
    "rawValue" JSONB NOT NULL DEFAULT '{}',
    "derivedSignals" JSONB NOT NULL DEFAULT '{}',
    "derivedContext" JSONB NOT NULL DEFAULT '{}',
    "runnerMetadata" JSONB NOT NULL DEFAULT '{}',
    "privacyLevel" TEXT NOT NULL DEFAULT 'anonymous',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SessionTraceEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ModelInferenceResult" (
    "id" TEXT NOT NULL,
    "decisionId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "modelVersion" TEXT NOT NULL DEFAULT 'rule_based_v1',
    "experimentId" TEXT,
    "candidateSetVersion" TEXT,
    "chosenActionId" TEXT,
    "rankedCandidates" JSONB NOT NULL DEFAULT '[]',
    "guardrailDecisions" JSONB NOT NULL DEFAULT '[]',
    "latencyMs" INTEGER NOT NULL,
    "riskScore" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ModelInferenceResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "InterventionExposure" (
    "id" TEXT NOT NULL,
    "exposureId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "decisionId" TEXT NOT NULL,
    "actionId" TEXT NOT NULL,
    "impressionTs" BIGINT,
    "dismissTs" BIGINT,
    "ctaTs" BIGINT,
    "renderSuccess" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "InterventionExposure_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "JourneyOutcome" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "outcome" TEXT NOT NULL,
    "terminalStepId" TEXT,
    "advisorRouted" BOOLEAN NOT NULL DEFAULT false,
    "converted" BOOLEAN NOT NULL DEFAULT false,
    "abandoned" BOOLEAN NOT NULL DEFAULT false,
    "endedAt" BIGINT,
    "finalTariff" TEXT,
    "finalVisiblePrice" DOUBLE PRECISION,
    "priceDelta" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "JourneyOutcome_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "SessionTraceEvent_eventId_key" ON "SessionTraceEvent"("eventId");

-- CreateIndex
CREATE INDEX "SessionTraceEvent_sessionId_idx" ON "SessionTraceEvent"("sessionId");

-- CreateIndex
CREATE INDEX "SessionTraceEvent_sessionId_ts_idx" ON "SessionTraceEvent"("sessionId", "ts");

-- CreateIndex
CREATE UNIQUE INDEX "ModelInferenceResult_decisionId_key" ON "ModelInferenceResult"("decisionId");

-- CreateIndex
CREATE INDEX "ModelInferenceResult_sessionId_idx" ON "ModelInferenceResult"("sessionId");

-- CreateIndex
CREATE UNIQUE INDEX "InterventionExposure_exposureId_key" ON "InterventionExposure"("exposureId");

-- CreateIndex
CREATE INDEX "InterventionExposure_sessionId_idx" ON "InterventionExposure"("sessionId");

-- CreateIndex
CREATE INDEX "InterventionExposure_decisionId_idx" ON "InterventionExposure"("decisionId");

-- CreateIndex
CREATE UNIQUE INDEX "JourneyOutcome_sessionId_key" ON "JourneyOutcome"("sessionId");

-- CreateIndex
CREATE INDEX "JourneyOutcome_outcome_idx" ON "JourneyOutcome"("outcome");
