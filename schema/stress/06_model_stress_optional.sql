-- Facultatif : exécuter APRÈS l'import, dans la base sélectionnée dans SSMS.
-- La cible représente les octets aléatoires, PAS la taille mesurée de Power BI.
-- Aucun changement des montants, clés, relations ou nombres de factures.
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @TargetRandomGiB decimal(9,3) = 1.500;
DECLARE @BatchSize int = 100;
DECLARE @RandomBytesPerRow int = 15000;
DECLARE @TargetRows bigint = CEILING(@TargetRandomGiB * 1073741824 / @RandomBytesPerRow);

IF OBJECT_ID(N'Activite.Factures', N'U') IS NULL
    THROW 51100, 'Sélectionnez la base ADV existante dans SSMS avant exécution.', 1;
IF @TargetRandomGiB <= 0 OR @BatchSize < 1
    THROW 51101, 'La cible et la taille de lot doivent être positives.', 1;
IF (SELECT COUNT_BIG(*) FROM [Activite].[Factures]) < @TargetRows
    THROW 51102, 'Pas assez de factures. Réduisez la cible ou régénérez plus de partitions. Aucune colonne ajoutée.', 1;

IF COL_LENGTH(N'Activite.Factures', N'ChargeTestModele') IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM sys.extended_properties
    WHERE major_id = OBJECT_ID(N'Activite.Factures')
      AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'Activite.Factures'), N'ChargeTestModele', 'ColumnId')
      AND name = N'KevserModelStress' AND CONVERT(nvarchar(128), value) = N'v1-hex-30000'
)
    THROW 51103, 'La colonne existe sans marqueur du kit. Arrêt pour préserver les données existantes.', 1;

IF COL_LENGTH(N'Activite.Factures', N'ChargeTestModele') IS NULL
BEGIN
    BEGIN TRANSACTION;
    ALTER TABLE [Activite].[Factures] ADD [ChargeTestModele] varchar(max) NULL;
    EXEC sys.sp_addextendedproperty
        @name=N'KevserModelStress', @value=N'v1-hex-30000',
        @level0type=N'SCHEMA', @level0name=N'Activite',
        @level1type=N'TABLE', @level1name=N'Factures',
        @level2type=N'COLUMN', @level2name=N'ChargeTestModele';
    COMMIT TRANSACTION;
END;
-- Nouvelle compilation après ALTER TABLE : la colonne peut être nouvelle.
EXEC sys.sp_executesql N'
IF EXISTS (SELECT 1 FROM [Activite].[Factures]
           WHERE [ChargeTestModele] IS NOT NULL AND DATALENGTH([ChargeTestModele]) <> 30000)
    THROW 51104, ''Charge existante incompatible : vérifiez la colonne avant de continuer.'', 1;

DECLARE @Existing bigint = (SELECT COUNT_BIG(*) FROM [Activite].[Factures]
                           WHERE [ChargeTestModele] IS NOT NULL);
DECLARE @Remaining bigint = CASE WHEN @TargetRows > @Existing THEN @TargetRows - @Existing ELSE 0 END;
SELECT TOP (@Remaining) [Id] INTO #Targets
FROM [Activite].[Factures] WHERE [ChargeTestModele] IS NULL ORDER BY [Id];
CREATE UNIQUE CLUSTERED INDEX IX_Targets ON #Targets ([Id]);
SELECT TOP (0) [Id] INTO #Batch FROM #Targets;
CREATE UNIQUE CLUSTERED INDEX IX_Batch ON #Batch ([Id]);

WHILE EXISTS (SELECT 1 FROM #Targets)
BEGIN
    TRUNCATE TABLE #Batch;
    INSERT INTO #Batch SELECT TOP (@BatchSize) [Id] FROM #Targets ORDER BY [Id];
    UPDATE f SET [ChargeTestModele] =
        CONVERT(varchar(max), CRYPT_GEN_RANDOM(7500), 2)
        + CONVERT(varchar(max), CRYPT_GEN_RANDOM(7500), 2)
    FROM [Activite].[Factures] f INNER JOIN #Batch b ON b.[Id] = f.[Id];
    DELETE t FROM #Targets t INNER JOIN #Batch b ON b.[Id] = t.[Id];
END;

IF (SELECT COUNT_BIG(*) FROM [Activite].[Factures] WHERE [ChargeTestModele] IS NOT NULL) < @TargetRows
    THROW 51105, ''La cible de charge n''''est pas atteinte.'', 1;
-- Vérifie un échantillon sans relire plusieurs Gio pour un comptage distinct.
SELECT TOP (1000) HASHBYTES(''SHA2_256'', [ChargeTestModele]) AS Empreinte
INTO #Sample FROM [Activite].[Factures] WHERE [ChargeTestModele] IS NOT NULL ORDER BY [Id];
IF (SELECT COUNT(DISTINCT Empreinte) FROM #Sample) <> (SELECT COUNT(*) FROM #Sample)
    THROW 51106, ''Des charges identiques sont détectées dans l''''échantillon. Test de cardinalité en échec.'', 1;
SELECT DB_NAME() AS BaseCible,
    COUNT_BIG(*) AS FacturesChargees,
    MIN(DATALENGTH([ChargeTestModele])) AS MinimumCaracteres,
    MAX(DATALENGTH([ChargeTestModele])) AS MaximumCaracteres,
    SUM(CONVERT(bigint, DATALENGTH([ChargeTestModele]))) AS OctetsTexteSQL,
    SUM(CONVERT(bigint, DATALENGTH([ChargeTestModele]))) / 1073741824.0 AS GiBTexteSQL,
    SUM(CONVERT(bigint, DATALENGTH([ChargeTestModele]))) / 2 / 1073741824.0 AS GiBOctetsAleatoires,
    ''Taille Power BI à mesurer après import complet de cette colonne'' AS VerificationPowerBI
FROM [Activite].[Factures] WHERE [ChargeTestModele] IS NOT NULL;
', N'@TargetRows bigint, @BatchSize int', @TargetRows, @BatchSize;
