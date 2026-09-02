-- CreateEnum
CREATE TYPE "GeoLevel" AS ENUM ('NATIONAL', 'PROVINCE', 'TERRITORY');

-- CreateEnum
CREATE TYPE "ProductivityMeasure" AS ENUM ('LABOUR_PRODUCTIVITY', 'MULTIFACTOR_PRODUCTIVITY', 'HOURS_WORKED', 'REAL_GDP', 'UNIT_LABOUR_COST');

-- CreateEnum
CREATE TYPE "PeriodType" AS ENUM ('ANNUAL', 'QUARTERLY', 'MONTHLY');

-- CreateEnum
CREATE TYPE "DataSource" AS ENUM ('STATCAN_WDS', 'MSC_GEOMET', 'CANADIAN_SURVEY_BUSINESS_CONDITIONS');

-- CreateEnum
CREATE TYPE "IngestionStatus" AS ENUM ('RUNNING', 'SUCCESS', 'FAILED');

-- CreateEnum
CREATE TYPE "IngestionMode" AS ENUM ('INITIAL', 'INCREMENTAL');

-- CreateTable
CREATE TABLE "Geography" (
    "id" TEXT NOT NULL,
    "sgcCode" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "level" "GeoLevel" NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Geography_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Industry" (
    "id" TEXT NOT NULL,
    "naicsCode" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "parentNaicsCode" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Industry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ProductivityObservation" (
    "id" TEXT NOT NULL,
    "geographyId" TEXT NOT NULL,
    "industryId" TEXT NOT NULL,
    "measure" "ProductivityMeasure" NOT NULL,
    "periodStart" TIMESTAMP(3) NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "value" DOUBLE PRECISION,
    "unit" TEXT NOT NULL,
    "source" "DataSource" NOT NULL,
    "sourceVectorId" TEXT,
    "sourceTableId" TEXT,
    "retrievedAt" TIMESTAMP(3) NOT NULL,
    "statusFlag" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ProductivityObservation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Covariate" (
    "id" TEXT NOT NULL,
    "geographyId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "periodStart" TIMESTAMP(3) NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "value" DOUBLE PRECISION,
    "unit" TEXT NOT NULL,
    "source" "DataSource" NOT NULL,
    "retrievedAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Covariate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ModelVersion" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "algorithm" TEXT NOT NULL,
    "trainingCutoff" TIMESTAMP(3) NOT NULL,
    "metricsJson" JSONB,
    "featureListJson" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ModelVersion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Forecast" (
    "id" TEXT NOT NULL,
    "modelVersionId" TEXT NOT NULL,
    "geographyId" TEXT NOT NULL,
    "industryId" TEXT NOT NULL,
    "measure" "ProductivityMeasure" NOT NULL,
    "forecastOrigin" TIMESTAMP(3) NOT NULL,
    "targetPeriod" TIMESTAMP(3) NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "predicted" DOUBLE PRECISION NOT NULL,
    "lowerBound" DOUBLE PRECISION,
    "upperBound" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Forecast_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DriverAttribution" (
    "id" TEXT NOT NULL,
    "modelVersionId" TEXT NOT NULL,
    "featureName" TEXT NOT NULL,
    "contribution" DOUBLE PRECISION NOT NULL,
    "contextJson" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DriverAttribution_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ScenarioRun" (
    "id" TEXT NOT NULL,
    "geographyId" TEXT NOT NULL,
    "industryId" TEXT NOT NULL,
    "measure" "ProductivityMeasure" NOT NULL,
    "adjustmentsJson" JSONB NOT NULL,
    "baselineValue" DOUBLE PRECISION NOT NULL,
    "simulatedValue" DOUBLE PRECISION NOT NULL,
    "modelVersionRef" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ScenarioRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "StatCanDataset" (
    "id" TEXT NOT NULL,
    "productId" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "tableRef" TEXT,
    "frequencyCode" INTEGER,
    "frequency" "PeriodType",
    "startDate" TIMESTAMP(3),
    "endDate" TIMESTAMP(3),
    "releaseTime" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "StatCanDataset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "StatCanIndustry" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "memberId" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "classificationCode" TEXT,
    "parentMemberId" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "StatCanIndustry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "StatCanGeography" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "memberId" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "classificationCode" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "StatCanGeography_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "StatCanMeasure" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "memberId" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "unitOfMeasure" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "StatCanMeasure_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "StatCanObservation" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "industryId" TEXT NOT NULL,
    "geographyId" TEXT NOT NULL,
    "measureId" TEXT NOT NULL,
    "periodStart" TIMESTAMP(3) NOT NULL,
    "periodLabel" TEXT NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "value" DOUBLE PRECISION,
    "unit" TEXT NOT NULL,
    "coordinate" TEXT NOT NULL,
    "vectorId" INTEGER,
    "refPeriodRaw" TEXT NOT NULL,
    "statusCode" TEXT,
    "symbolCode" TEXT,
    "scalarFactorCode" INTEGER,
    "retrievedAt" TIMESTAMP(3) NOT NULL,
    "ingestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ingestionRunId" TEXT,

    CONSTRAINT "StatCanObservation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SourceMetadata" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "sourceMethod" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "dimensionCount" INTEGER NOT NULL,
    "memberCount" INTEGER NOT NULL,
    "retrievedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SourceMetadata_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "IngestionRun" (
    "id" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "status" "IngestionStatus" NOT NULL DEFAULT 'RUNNING',
    "mode" "IngestionMode" NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "observationsDownloaded" INTEGER NOT NULL DEFAULT 0,
    "observationsInserted" INTEGER NOT NULL DEFAULT 0,
    "observationsUpdated" INTEGER NOT NULL DEFAULT 0,
    "duplicatesSkipped" INTEGER NOT NULL DEFAULT 0,
    "rowsRejected" INTEGER NOT NULL DEFAULT 0,
    "missingValues" INTEGER NOT NULL DEFAULT 0,
    "earliestPeriod" TIMESTAMP(3),
    "latestPeriod" TIMESTAMP(3),
    "industriesDiscovered" INTEGER NOT NULL DEFAULT 0,
    "measuresDiscovered" INTEGER NOT NULL DEFAULT 0,
    "durationSeconds" DOUBLE PRECISION,
    "errorMessage" TEXT,

    CONSTRAINT "IngestionRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Geography_sgcCode_key" ON "Geography"("sgcCode");

-- CreateIndex
CREATE INDEX "Geography_level_idx" ON "Geography"("level");

-- CreateIndex
CREATE UNIQUE INDEX "Industry_naicsCode_key" ON "Industry"("naicsCode");

-- CreateIndex
CREATE INDEX "Industry_parentNaicsCode_idx" ON "Industry"("parentNaicsCode");

-- CreateIndex
CREATE INDEX "ProductivityObservation_measure_periodStart_idx" ON "ProductivityObservation"("measure", "periodStart");

-- CreateIndex
CREATE UNIQUE INDEX "ProductivityObservation_geographyId_industryId_measure_peri_key" ON "ProductivityObservation"("geographyId", "industryId", "measure", "periodStart", "periodType");

-- CreateIndex
CREATE INDEX "Covariate_name_periodStart_idx" ON "Covariate"("name", "periodStart");

-- CreateIndex
CREATE UNIQUE INDEX "Covariate_geographyId_name_periodStart_periodType_key" ON "Covariate"("geographyId", "name", "periodStart", "periodType");

-- CreateIndex
CREATE UNIQUE INDEX "ModelVersion_name_version_key" ON "ModelVersion"("name", "version");

-- CreateIndex
CREATE INDEX "Forecast_geographyId_industryId_measure_targetPeriod_idx" ON "Forecast"("geographyId", "industryId", "measure", "targetPeriod");

-- CreateIndex
CREATE INDEX "DriverAttribution_modelVersionId_featureName_idx" ON "DriverAttribution"("modelVersionId", "featureName");

-- CreateIndex
CREATE INDEX "ScenarioRun_geographyId_industryId_measure_idx" ON "ScenarioRun"("geographyId", "industryId", "measure");

-- CreateIndex
CREATE UNIQUE INDEX "StatCanDataset_productId_key" ON "StatCanDataset"("productId");

-- CreateIndex
CREATE INDEX "StatCanIndustry_datasetId_idx" ON "StatCanIndustry"("datasetId");

-- CreateIndex
CREATE INDEX "StatCanIndustry_name_idx" ON "StatCanIndustry"("name");

-- CreateIndex
CREATE UNIQUE INDEX "StatCanIndustry_datasetId_memberId_key" ON "StatCanIndustry"("datasetId", "memberId");

-- CreateIndex
CREATE INDEX "StatCanGeography_datasetId_idx" ON "StatCanGeography"("datasetId");

-- CreateIndex
CREATE INDEX "StatCanGeography_name_idx" ON "StatCanGeography"("name");

-- CreateIndex
CREATE UNIQUE INDEX "StatCanGeography_datasetId_memberId_key" ON "StatCanGeography"("datasetId", "memberId");

-- CreateIndex
CREATE INDEX "StatCanMeasure_datasetId_idx" ON "StatCanMeasure"("datasetId");

-- CreateIndex
CREATE INDEX "StatCanMeasure_name_idx" ON "StatCanMeasure"("name");

-- CreateIndex
CREATE UNIQUE INDEX "StatCanMeasure_datasetId_memberId_key" ON "StatCanMeasure"("datasetId", "memberId");

-- CreateIndex
CREATE INDEX "StatCanObservation_periodStart_idx" ON "StatCanObservation"("periodStart");

-- CreateIndex
CREATE INDEX "StatCanObservation_industryId_idx" ON "StatCanObservation"("industryId");

-- CreateIndex
CREATE INDEX "StatCanObservation_geographyId_idx" ON "StatCanObservation"("geographyId");

-- CreateIndex
CREATE INDEX "StatCanObservation_measureId_idx" ON "StatCanObservation"("measureId");

-- CreateIndex
CREATE INDEX "StatCanObservation_datasetId_measureId_periodStart_idx" ON "StatCanObservation"("datasetId", "measureId", "periodStart");

-- CreateIndex
CREATE UNIQUE INDEX "StatCanObservation_datasetId_coordinate_periodStart_key" ON "StatCanObservation"("datasetId", "coordinate", "periodStart");

-- CreateIndex
CREATE INDEX "SourceMetadata_datasetId_idx" ON "SourceMetadata"("datasetId");

-- CreateIndex
CREATE INDEX "IngestionRun_datasetId_startedAt_idx" ON "IngestionRun"("datasetId", "startedAt");

-- AddForeignKey
ALTER TABLE "ProductivityObservation" ADD CONSTRAINT "ProductivityObservation_geographyId_fkey" FOREIGN KEY ("geographyId") REFERENCES "Geography"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ProductivityObservation" ADD CONSTRAINT "ProductivityObservation_industryId_fkey" FOREIGN KEY ("industryId") REFERENCES "Industry"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Covariate" ADD CONSTRAINT "Covariate_geographyId_fkey" FOREIGN KEY ("geographyId") REFERENCES "Geography"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Forecast" ADD CONSTRAINT "Forecast_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Forecast" ADD CONSTRAINT "Forecast_geographyId_fkey" FOREIGN KEY ("geographyId") REFERENCES "Geography"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Forecast" ADD CONSTRAINT "Forecast_industryId_fkey" FOREIGN KEY ("industryId") REFERENCES "Industry"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DriverAttribution" ADD CONSTRAINT "DriverAttribution_modelVersionId_fkey" FOREIGN KEY ("modelVersionId") REFERENCES "ModelVersion"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ScenarioRun" ADD CONSTRAINT "ScenarioRun_geographyId_fkey" FOREIGN KEY ("geographyId") REFERENCES "Geography"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ScenarioRun" ADD CONSTRAINT "ScenarioRun_industryId_fkey" FOREIGN KEY ("industryId") REFERENCES "Industry"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanIndustry" ADD CONSTRAINT "StatCanIndustry_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanGeography" ADD CONSTRAINT "StatCanGeography_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanMeasure" ADD CONSTRAINT "StatCanMeasure_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanObservation" ADD CONSTRAINT "StatCanObservation_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanObservation" ADD CONSTRAINT "StatCanObservation_industryId_fkey" FOREIGN KEY ("industryId") REFERENCES "StatCanIndustry"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanObservation" ADD CONSTRAINT "StatCanObservation_geographyId_fkey" FOREIGN KEY ("geographyId") REFERENCES "StatCanGeography"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanObservation" ADD CONSTRAINT "StatCanObservation_measureId_fkey" FOREIGN KEY ("measureId") REFERENCES "StatCanMeasure"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "StatCanObservation" ADD CONSTRAINT "StatCanObservation_ingestionRunId_fkey" FOREIGN KEY ("ingestionRunId") REFERENCES "IngestionRun"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SourceMetadata" ADD CONSTRAINT "SourceMetadata_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IngestionRun" ADD CONSTRAINT "IngestionRun_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "StatCanDataset"("id") ON DELETE CASCADE ON UPDATE CASCADE;
