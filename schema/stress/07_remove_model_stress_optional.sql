-- Facultatif : retire uniquement la charge du kit, dans la base sélectionnée.
SET XACT_ABORT ON;
IF COL_LENGTH(N'Activite.Factures', N'ChargeTestModele') IS NOT NULL
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.extended_properties
        WHERE major_id = OBJECT_ID(N'Activite.Factures')
          AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'Activite.Factures'), N'ChargeTestModele', 'ColumnId')
          AND name = N'KevserModelStress' AND CONVERT(nvarchar(128), value) = N'v1-hex-30000'
    )
        THROW 51103, 'La colonne ne porte pas le marqueur du kit. Suppression refusée.', 1;
    ALTER TABLE [Activite].[Factures] DROP COLUMN [ChargeTestModele];
END;
SELECT DB_NAME() AS BaseCible,
    CASE WHEN COL_LENGTH(N'Activite.Factures', N'ChargeTestModele') IS NULL
         THEN 'Charge supprimée' ELSE 'Charge encore présente' END AS Resultat;
