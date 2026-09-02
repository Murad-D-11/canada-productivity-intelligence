-- CreateEnum
CREATE TYPE "WeatherVariable" AS ENUM ('TEMPERATURE', 'PRECIPITATION', 'SNOWFALL', 'WIND_SPEED');

-- CreateTable
CREATE TABLE "WeatherStation" (
    "id" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "province" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "elevation" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "WeatherStation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "WeatherObservation" (
    "id" TEXT NOT NULL,
    "stationId" TEXT NOT NULL,
    "province" TEXT NOT NULL,
    "periodStart" TIMESTAMP(3) NOT NULL,
    "periodLabel" TEXT NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "variable" "WeatherVariable" NOT NULL,
    "value" DOUBLE PRECISION,
    "unit" TEXT NOT NULL,
    "aggregation" TEXT NOT NULL,
    "sampleCount" INTEGER NOT NULL DEFAULT 0,
    "source" "DataSource" NOT NULL DEFAULT 'MSC_GEOMET',
    "collectionId" TEXT,
    "retrievedAt" TIMESTAMP(3) NOT NULL,
    "ingestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ingestionRunId" TEXT,

    CONSTRAINT "WeatherObservation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "WeatherIngestionRun" (
    "id" TEXT NOT NULL,
    "status" "IngestionStatus" NOT NULL DEFAULT 'RUNNING',
    "mode" "IngestionMode" NOT NULL,
    "collectionId" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "observationsDownloaded" INTEGER NOT NULL DEFAULT 0,
    "observationsInserted" INTEGER NOT NULL DEFAULT 0,
    "observationsUpdated" INTEGER NOT NULL DEFAULT 0,
    "duplicatesSkipped" INTEGER NOT NULL DEFAULT 0,
    "rowsRejected" INTEGER NOT NULL DEFAULT 0,
    "missingValues" INTEGER NOT NULL DEFAULT 0,
    "stationsDiscovered" INTEGER NOT NULL DEFAULT 0,
    "earliestPeriod" TIMESTAMP(3),
    "latestPeriod" TIMESTAMP(3),
    "durationSeconds" DOUBLE PRECISION,
    "errorMessage" TEXT,

    CONSTRAINT "WeatherIngestionRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FeatureSet" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "periodCutoff" TIMESTAMP(3) NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "featureListJson" JSONB NOT NULL,
    "rowCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "FeatureSet_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FeatureRow" (
    "id" TEXT NOT NULL,
    "featureSetId" TEXT NOT NULL,
    "industry" TEXT NOT NULL,
    "geography" TEXT NOT NULL,
    "measure" TEXT NOT NULL,
    "periodStart" TIMESTAMP(3) NOT NULL,
    "periodLabel" TEXT NOT NULL,
    "periodType" "PeriodType" NOT NULL,
    "targetValue" DOUBLE PRECISION,
    "prodLag1" DOUBLE PRECISION,
    "prodLag4" DOUBLE PRECISION,
    "prodRollMean4" DOUBLE PRECISION,
    "employmentGrowth" DOUBLE PRECISION,
    "labourCostGrowth" DOUBLE PRECISION,
    "quarter" INTEGER,
    "month" INTEGER,
    "weatherTempMean" DOUBLE PRECISION,
    "weatherPrecipSum" DOUBLE PRECISION,
    "weatherSnowfallSum" DOUBLE PRECISION,
    "weatherWindMean" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "FeatureRow_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "WeatherStation_province_idx" ON "WeatherStation"("province");

-- CreateIndex
CREATE UNIQUE INDEX "WeatherStation_stationId_key" ON "WeatherStation"("stationId");

-- CreateIndex
CREATE INDEX "WeatherObservation_periodStart_idx" ON "WeatherObservation"("periodStart");

-- CreateIndex
CREATE INDEX "WeatherObservation_province_idx" ON "WeatherObservation"("province");

-- CreateIndex
CREATE INDEX "WeatherObservation_variable_idx" ON "WeatherObservation"("variable");

-- CreateIndex
CREATE INDEX "WeatherObservation_province_variable_periodStart_idx" ON "WeatherObservation"("province", "variable", "periodStart");

-- CreateIndex
CREATE UNIQUE INDEX "WeatherObservation_stationId_periodStart_variable_key" ON "WeatherObservation"("stationId", "periodStart", "variable");

-- CreateIndex
CREATE INDEX "WeatherIngestionRun_collectionId_startedAt_idx" ON "WeatherIngestionRun"("collectionId", "startedAt");

-- CreateIndex
CREATE INDEX "FeatureSet_name_createdAt_idx" ON "FeatureSet"("name", "createdAt");

-- CreateIndex
CREATE INDEX "FeatureRow_periodStart_idx" ON "FeatureRow"("periodStart");

-- CreateIndex
CREATE INDEX "FeatureRow_industry_measure_periodStart_idx" ON "FeatureRow"("industry", "measure", "periodStart");

-- CreateIndex
CREATE UNIQUE INDEX "FeatureRow_featureSetId_industry_geography_measure_periodSt_key" ON "FeatureRow"("featureSetId", "industry", "geography", "measure", "periodStart");

-- AddForeignKey
ALTER TABLE "WeatherObservation" ADD CONSTRAINT "WeatherObservation_stationId_fkey" FOREIGN KEY ("stationId") REFERENCES "WeatherStation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "WeatherObservation" ADD CONSTRAINT "WeatherObservation_ingestionRunId_fkey" FOREIGN KEY ("ingestionRunId") REFERENCES "WeatherIngestionRun"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FeatureRow" ADD CONSTRAINT "FeatureRow_featureSetId_fkey" FOREIGN KEY ("featureSetId") REFERENCES "FeatureSet"("id") ON DELETE CASCADE ON UPDATE CASCADE;
