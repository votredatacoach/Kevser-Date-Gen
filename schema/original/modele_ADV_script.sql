use Adventure


IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'Activite')
    EXEC('CREATE SCHEMA Activite');
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'Referentiel')
    EXEC('CREATE SCHEMA Referentiel');
GO

CREATE TABLE [Activite].[Agences] (
    [Id] uniqueidentifier,
    [Nom] nvarchar(50),
    [Code] nvarchar(3),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [Mail] nvarchar(255),
    [IndicatifTelephone] nvarchar(5),
    [Telephone] nvarchar(20),
    [IndicatifFax] nvarchar(5),
    [Fax] nvarchar(20),
    [DossierAgencePrincipalId] uniqueidentifier,
    [IsGeneraliste] bit,
    [IsCertifieCefri] bit,
    [TypeAgence] int,
    [NbJoursValiditeNssProvisoire] int,
    CONSTRAINT [PK_Activite.Agences] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[AxesAnalytiques] (
    [Id] uniqueidentifier,
    [Code] nvarchar(20),
    [FamilleCode] nvarchar(20),
    [Valeur] nvarchar(50),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [EtablissementClientId] uniqueidentifier,
    [ClientId] uniqueidentifier,
    [Discriminator] nvarchar(128),
    [AdresseLibelle] nvarchar(MAX),
    [AdresseLigne1] nvarchar(MAX),
    [AdresseLigne2] nvarchar(MAX),
    [AdresseLigne3] nvarchar(MAX),
    [PaysCode] nvarchar(MAX),
    [IsCedex] bit,
    [CodePostal] nvarchar(MAX),
    [UtilisationAdresseSpecifique] bit,
    [Ville] nvarchar(MAX),
    [IsActif] bit,
    CONSTRAINT [PK_Activite.AxesAnalytiques] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[Clients] (
    [Id] uniqueidentifier,
    [Matricule] int,
    [SIREN] nvarchar(50),
    [CodeAPE] nvarchar(10),
    [FormeJuridiqueCode] nvarchar(10),
    [RaisonSociale] nvarchar(100),
    [AdresseLigne1] nvarchar(100),
    [AdresseLigne2] nvarchar(100),
    [AdresseLigne3] nvarchar(100),
    [CodePostal] nvarchar(15),
    [Ville] nvarchar(50),
    [PaysCode] nchar(2),
    [IndicatifTelephone] nvarchar(5),
    [Telephone] nvarchar(20),
    [IndicatifFax] nvarchar(5),
    [Fax] nvarchar(20),
    [CentrePayeurCode] nvarchar(5),
    [IsBlocage] bit,
    [IsDecompteValide] bit,
    [MotifBlocageCode] nvarchar(5),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsCpCedex] bit,
    [IdAdequat] nvarchar(50),
    [TypeEntrepriseCode] nvarchar(10),
    [ParametrageFacturationId] uniqueidentifier,
    [ParametrageSpecificitesId] uniqueidentifier,
    [NoteEllipro] int,
    [IsNoteElliproReadOnly] bit,
    [CommentaireSiren] nvarchar(MAX),
    [CedexId] bigint,
    [CommuneId] int,
    [IsVerificationJourManquantDesactivee] bit,
    [StatutDiffusion] int,
    [EtatAdministratif] int,
    CONSTRAINT [PK_Activite.Clients] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[ContratsModelesPoste] (
    [Id] uniqueidentifier,
    [CategorieCode] nvarchar(10),
    [ProfilPaieCode] nvarchar(10),
    [CategorieClientCode] nvarchar(10),
    [QualificationCode] nvarchar(20),
    [NiveauQualif] nvarchar(2),
    [PositionQualif] nvarchar(3),
    [CoeffQualif] nvarchar(3),
    [AutreQualif] nvarchar(3),
    [IsQualifRisque] bit,
    [DetailRisque] nvarchar(255),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [EtablissementClientId] uniqueidentifier,
    [InterimaireId] uniqueidentifier,
    [DossierAgenceId] uniqueidentifier,
    [Etat] int,
    [EtatImpression] int,
    [Numero] int,
    [DepartementEtablissementClientId] uniqueidentifier,
    [HorairesAnael] nvarchar(MAX),
    [ContratDupliqueId] uniqueidentifier,
    [Libelle] nvarchar(100),
    [ClientIdModelePoste] uniqueidentifier,
    [EtablissementClientIdModelePoste] uniqueidentifier,
    [Discriminator] nvarchar(128),
    [CommercialId] uniqueidentifier,
    [Commande] nvarchar(30),
    [AgenceOrigineId] uniqueidentifier,
    [CdiInterimaireId] uniqueidentifier,
    [TypeDecompteCode] nvarchar(10),
    [QualificationLibre] nvarchar(50),
    [DpaeId] uniqueidentifier,
    [QualificationPixid] nvarchar(25),
    [CategoriesPixid] nvarchar(25),
    [RecruteurId] uniqueidentifier,
    [IsGed] bit,
    [IsDoubleDecompte] bit,
    [DatePremiereMiseEnContrat] datetime2,
    [Annexes] nvarchar(MAX),
    [ContratApprentissageInterimaireId] uniqueidentifier,
    [ApporteurAffairesId] uniqueidentifier,
    [TauxInteressement] decimal,
    [ReferentielRubriqueClientId] int,
    [PerimetreReferentielId] uniqueidentifier,
    [CommandePlateformeInterimaireId] bigint,
    [AccordCadreId] int,
    [AllianceCodeClient] nvarchar(100),
    [CandidatExpressionBesoinId] bigint,
    [RetourSignatureId] bigint,
    [AgenceGestionnaireId] uniqueidentifier,
    CONSTRAINT [PK_Activite.ContratsModelesPoste] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[DepartementsEtablissementsClients] (
    [Id] uniqueidentifier,
    [Libelle] nvarchar(100),
    [AdresseLigne1] nvarchar(100),
    [AdresseLigne2] nvarchar(100),
    [AdresseLigne3] nvarchar(100),
    [CodePostal] nvarchar(15),
    [Ville] nvarchar(50),
    [PaysCode] nchar(2),
    [EtablissementClientId] uniqueidentifier,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsCpCedex] bit,
    [CedexId] bigint,
    [CommuneId] int,
    CONSTRAINT [PK_Activite.DepartementsEtablissementsClients] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[DonneesContrat] (
    [ContratId] uniqueidentifier,
    [MotifFinContratCode] nvarchar(10),
    [OptionFinContratCpCode] nvarchar(10),
    [OptionFinContratIfmCode] nvarchar(10),
    [Justificatif] nvarchar(MAX),
    [NomPersonneRemplacee] nvarchar(MAX),
    [QualifCodePersonneRemplacee] nvarchar(20),
    [CategorieCodePersonneRemplacee] nvarchar(10),
    [TextePersonneRemplacee] nvarchar(MAX),
    [DateDebut] datetime2,
    [DateFinInitiale] datetime2,
    [DateFin] datetime2,
    [DateFinReelle] datetime2,
    [DateFinPeriodeEssai] datetime2,
    [DateSouplesseMin] datetime2,
    [DateSouplesseMax] datetime2,
    [DateTheoriqueReprise] datetime2,
    [MotifAnnulationContratCode] nvarchar(10),
    [CommentaireAnnulation] nvarchar(100),
    [NbJourPeriodeEssai] int,
    [NbJourSouplesseMin] int,
    [NbJourSouplesseMax] int,
    [NbJourCarence] int,
    [TypeContratCode] nvarchar(10),
    [MotifContratCode] nvarchar(10),
    [TermeCode] nvarchar(10),
    [HeureDebut] nvarchar(5),
    [JrTravailleLun] bit,
    [JrTravailleMar] bit,
    [JrTravailleMer] bit,
    [JrTravailleJeu] bit,
    [JrTravailleVen] bit,
    [JrTravailleSam] bit,
    [JrTravailleDim] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [QualifPersonneRemplaceeAutre] nvarchar(100),
    [IsQualifPersonneRemplaceeAutre] bit,
    [NomMaitreApprentissageEu] nvarchar(MAX),
    [PrenomMaitreApprentissageEu] nvarchar(MAX),
    [DiplomeMaitreApprentissageEu] nvarchar(MAX),
    [AnneesExpMaitreApprentissageEu] int,
    [NomMaitreApprentissageEtt] nvarchar(MAX),
    [PrenomMaitreApprentissageEtt] nvarchar(MAX),
    [DateSouplesseMaxContratAvenant] datetime2,
    [DateFinPrevisionnelle] datetime2,
    [PrecisionMotifFinContratCode] nvarchar(15),
    [IsRefusCdi] bit,
    [MotifFinContratPrevisionnelCode] nvarchar(10),
    [PrecisionMotifFinContratPrevisionnelleCode] nvarchar(15),
    [OptionFinContratCpPrevisionnelleCode] nvarchar(10),
    [OptionFinContratIfmPrevisionnelleCode] nvarchar(10),
    CONSTRAINT [PK_Activite.DonneesContrat] PRIMARY KEY CLUSTERED ([ContratId])
);

CREATE TABLE [Activite].[DossierAgenceMatriculeInterimaires] (
    [DossierAgenceId] uniqueidentifier,
    [Matricule] int,
    [RowVersion] timestamp,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    CONSTRAINT [PK_Activite.DossierAgenceMatriculeInterimaires] PRIMARY KEY CLUSTERED ([DossierAgenceId])
);

CREATE TABLE [Activite].[DossiersAgence] (
    [Id] uniqueidentifier,
    [Code] nvarchar(5),
    [Nom] nvarchar(50),
    [AgenceId] uniqueidentifier,
    [EtablissementId] uniqueidentifier,
    [IsProduction] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsApporteurAffaires] bit,
    CONSTRAINT [PK_Activite.DossiersAgence] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[Etablissements] (
    [Id] uniqueidentifier,
    [RaisonSociale] nvarchar(150),
    [SocieteId] uniqueidentifier,
    [EstAlsaceMoselle] bit,
    [CodeAPE] nvarchar(10),
    [Telephone] nvarchar(20),
    [Fax] nvarchar(20),
    [AdresseLigne1] nvarchar(100),
    [AdresseLigne2] nvarchar(100),
    [AdresseLigne3] nvarchar(100),
    [CodePostal] nvarchar(10),
    [Ville] nvarchar(100),
    [PaysCode] nchar(2),
    [CodeCentreVisiteMedicale] nvarchar(20),
    [CodeUrssaf] nvarchar(3),
    [DescriptionPoleEmploi] nvarchar(100),
    [PseudoSIRET] nvarchar(MAX),
    [DateDebutActivite] datetime2,
    [DateFinActivite] datetime2,
    [Code] nvarchar(3),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [NumeroCotisant] nvarchar(MAX),
    [CodeUrssafVlu] nvarchar(3),
    [CodeUrssafDpae] nvarchar(3),
    [NIC] nvarchar(5),
    [IndicatifTelephone] nvarchar(5),
    [IndicatifFax] nvarchar(5),
    [Etat] int,
    [PrefectureId] uniqueidentifier,
    [Nom] nvarchar(50),
    [Prenom] nvarchar(50),
    [MarqueCode] nvarchar(3),
    [Latitude] float,
    [Longitude] float,
    [GeocodeScore] int,
    [CommuneId] int,
    CONSTRAINT [PK_Activite.Etablissements] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[EtablissementsClient] (
    [Id] uniqueidentifier,
    [CodeNIC] nvarchar(5),
    [SIRET] nvarchar(55),
    [RaisonSociale] nvarchar(100),
    [AdresseLigne1] nvarchar(100),
    [AdresseLigne2] nvarchar(100),
    [AdresseLigne3] nvarchar(100),
    [CodePostal] nvarchar(15),
    [Ville] nvarchar(50),
    [PaysCode] nchar(2),
    [IndicatifTelephone] nvarchar(5),
    [Telephone] nvarchar(20),
    [IndicatifFax] nvarchar(5),
    [Fax] nvarchar(20),
    [IsAdresseSpecifique] bit,
    [IsBlocage] bit,
    [IsDecompteValide] bit,
    [ClientId] uniqueidentifier,
    [CentrePayeurCode] nvarchar(5),
    [MotifBlocageCode] nvarchar(5),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [Longitude] float,
    [Latitude] float,
    [ContactExploitation] nvarchar(100),
    [IsCpCedex] bit,
    [ParametrageFacturationId] uniqueidentifier,
    [ParametrageSpecificitesId] uniqueidentifier,
    [CedexId] bigint,
    [CommuneId] int,
    [HiresweetId] uniqueidentifier,
    [PlateformeId] bigint,
    [StatutDiffusion] int,
    [EtatAdministratif] int,
    CONSTRAINT [PK_Activite.EtablissementsClient] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[EtablissementsClientDossiersAgence] (
    [EtablissementClientId] uniqueidentifier,
    [DossierAgenceId] uniqueidentifier,
    [Matricule] int,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [ParametrageFacturationId] uniqueidentifier,
    [ParametrageSpecificitesId] uniqueidentifier,
    [PublicId] uniqueidentifier,
    CONSTRAINT [PK_Activite.EtablissementsClientDossiersAgence] PRIMARY KEY CLUSTERED ([EtablissementClientId], [DossierAgenceId])
);

CREATE TABLE [Activite].[Factures] (
    [Id] uniqueidentifier,
    [Numero] int,
    [DateEdition] datetime2,
    [DateReglement] datetime2,
    [EtablissementId] uniqueidentifier,
    [ClientId] uniqueidentifier,
    [EtablissementClientId] uniqueidentifier,
    [NumeroComplet] nvarchar(20),
    [IdParent] uniqueidentifier,
    [HasAvoir] bit,
    [IsAvoir] bit,
    [IsRefacturation] bit,
    [HasRefacturation] bit,
    [LotId] int,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [CriteresRupture] nvarchar(MAX),
    [TraiteId] uniqueidentifier,
    [DepartementClientId] uniqueidentifier,
    [SpecialisationDossierAgenceId] uniqueidentifier,
    [CommandePrestationId] uniqueidentifier,
    [NetAFacturer] decimal,
    [AgenceId] uniqueidentifier,
    [IsReglee] bit,
    [MontantHt] decimal,
    [AllianceCodeClient] nvarchar(100),
    CONSTRAINT [PK_Activite.Factures] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[GroupesClients] (
    [Description] nvarchar(50),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [DateDebut] datetime2,
    [DateFin] datetime2,
    [PiloteComptePrincipalId] uniqueidentifier,
    [PiloteComptePrincipalFonctionCode] nvarchar(5),
    [SegmentCode] nvarchar(5),
    [Id] int,
    [TypeGroupeCode] nvarchar(10),
    CONSTRAINT [PK_Activite.GroupesClients] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[HorairesEtCouts] (
    [ContratId] uniqueidentifier,
    [HoraireDebut] nvarchar(5),
    [HoraireFin] nvarchar(5),
    [HoraireDebut1] nvarchar(5),
    [HoraireFin1] nvarchar(5),
    [ComplementHoraire] nvarchar(255),
    [PeriodeNonTravaillee] nvarchar(255),
    [DureeHebdo] decimal,
    [IsDureeHebdoImprimerSurContrat] bit,
    [IsTempsPlein] bit,
    [SalaireReference] decimal,
    [BaseSalaireReference] decimal,
    [PrimeReference] nvarchar(255),
    [SalaireRemuneration] decimal,
    [BaseSalaireRemuneration] decimal,
    [TypeCoefficientCode] nvarchar(10),
    [Coefficient] decimal,
    [IsCoeffImprimerSurContrat] bit,
    [AxeAnalytiqueId] uniqueidentifier,
    [CycleHoraireId] uniqueidentifier,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsPeriodeNonTravailleeRemuneree] bit,
    [ModeleHoraireCycleHoraireId] uniqueidentifier,
    [Descriptif] nvarchar(100),
    [IsHeuresComplementairesAutorisees] bit,
    [UniteSalaire] int,
    [SalaireAnnuel] decimal,
    [NombreJourTravail] decimal,
    [NombreJourRtt] decimal,
    [NombreMois] decimal,
    [TreiziemeMoisJournalier] decimal,
    [ContexteId] int,
    [OrganisationParticuliereTempsTravail] nvarchar(255),
    [NombreJourRtt2] decimal,
    [NombreJourRtt3] decimal,
    CONSTRAINT [PK_Activite.HorairesEtCouts] PRIMARY KEY CLUSTERED ([ContratId])
);

CREATE TABLE [Activite].[Interimaires] (
    [Id] uniqueidentifier,
    [CodeRecruteur] nvarchar(50),
    [Civilite] int,
    [Nom] nvarchar(50),
    [NomJeuneFille] nvarchar(50),
    [Prenom] nvarchar(50),
    [IndicatifTelephone] nvarchar(5),
    [Telephone] nvarchar(20),
    [Email] nvarchar(255),
    [PaysNationaliteCode] nchar(2),
    [Commentaires] nvarchar(1000),
    [DateDisponibiliteAutre] datetime2,
    [CommentaireDisponibilite] nvarchar(255),
    [NumeroSecuriteSociale] nvarchar(50),
    [DateNaissance] datetime2,
    [DepartementNaissanceCode] nchar(3),
    [VilleNaissance] nvarchar(50),
    [PaysNaissanceCode] nchar(2),
    [Adresse] nvarchar(100),
    [ComplementAdresse] nvarchar(100),
    [CodePostal] nvarchar(15),
    [Ville] nvarchar(50),
    [PaysCode] nchar(2),
    [IndicatifTelephone2] nvarchar(5),
    [Telephone2] nvarchar(20),
    [LibelleTelephone2] nvarchar(50),
    [IndicatifTelephone3] nvarchar(5),
    [Telephone3] nvarchar(20),
    [LibelleTelephone3] nvarchar(50),
    [SituationFamilialeCode] nchar(1),
    [NombrePersonnesACharge] int,
    [MotifBlocageCode] nvarchar(5),
    [CommentaireBlocage] nvarchar(255),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [DateDisponibiliteTheorique] datetime2,
    [TypeDateDisponibilite] int,
    [NttTransmis] bit,
    [FullNameSearch] nvarchar(4000),
    [SourceRecrutementId] int,
    [Statut] int,
    [DateInscription] date,
    [DateDerniereCandidature] date,
    CONSTRAINT [PK_Activite.Interimaires] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[LieuMission] (
    [ContratId] uniqueidentifier,
    [NomOrganisme] nvarchar(100),
    [AdresseLigne1LieuMission] nvarchar(100),
    [AdresseLigne2LieuMission] nvarchar(100),
    [AdresseLigne3LieuMission] nvarchar(100),
    [CodePostalLieuMission] nvarchar(10),
    [VilleLieuMission] nvarchar(100),
    [PaysCodeLieuMission] nchar(2),
    [PersonneDemandee] nvarchar(100),
    [Contact] nvarchar(200),
    [MoyenAcces] nvarchar(100),
    [DestinataireEnvoiContrat] nvarchar(100),
    [AdresseLigne1EnvoiContrat] nvarchar(100),
    [AdresseLigne2EnvoiContrat] nvarchar(100),
    [AdresseLigne3EnvoiContrat] nvarchar(100),
    [CodePostalEnvoiContrat] nvarchar(10),
    [VilleEnvoiContrat] nvarchar(100),
    [PaysCodeEnvoiContrat] nchar(2),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsCpCedexLieuMission] bit,
    [IsCpCedexEnvoiContrat] bit,
    [CedexIdLieuMission] bigint,
    [CommuneIdLieuMission] int,
    [CedexIdEnvoiContrat] bigint,
    [CommuneIdEnvoiContrat] int,
    CONSTRAINT [PK_Activite.LieuMission] PRIMARY KEY CLUSTERED ([ContratId])
);

CREATE TABLE [Activite].[LignesFacture] (
    [Id] int,
    [FactureId] uniqueidentifier,
    [RubriqueId] int,
    [ContratId] uniqueidentifier,
    [LigneRhId] uniqueidentifier,
    [Base] decimal,
    [Taux] decimal,
    [MontantTTC] decimal,
    [MontantHT] decimal,
    [TauxTVA] decimal,
    [TVA] decimal,
    [Coefficient] decimal,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [LignePrestationId] uniqueidentifier,
    [BibliothequeMappingRubriqueId] uniqueidentifier,
    CONSTRAINT [PK_Activite.LignesFacture] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[LignesReleveHeures] (
    [Id] uniqueidentifier,
    [ReleveHeuresId] uniqueidentifier,
    [PartieSemaine] nchar(1),
    [RubriqueId] int,
    [BasePaie] decimal,
    [BaseFact] decimal,
    [TauxPaie] decimal,
    [TauxFact] decimal,
    [MontantPaie] decimal,
    [MontantFact] decimal,
    [Coefficient] decimal,
    [LotPaieId] int,
    [LotFactureId] int,
    [AxeAnalytiqueId] uniqueidentifier,
    [VentilationReleveHeuresId] uniqueidentifier,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsRegularisation] bit,
    [MergeId] uniqueidentifier,
    [BibliothequeMappingRubriqueId] uniqueidentifier,
    [IsMontantAuCet] bit,
    CONSTRAINT [PK_Activite.LignesReleveHeures] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[LotsFacturation] (
    [Id] int,
    [TypeTraitementFacturation] int,
    [Description] nvarchar(128),
    [Etat] int,
    [DateTraitement] datetime2,
    [DateComptable] date,
    [DateArrete] date,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [ModeSelection] int,
    [DateArreteSemaine] datetime2,
    [DateArreteMois] datetime2,
    [DateArreteSemaineTronquee] datetime2,
    [DateArreteSpecifique] datetime2,
    [DateReglementSemaine] datetime2,
    [DateReglementMois] datetime2,
    [DateReglementSemaineTronquee] datetime2,
    [DateReglementSpecifique] datetime2,
    [DateArreteSemaineMultiple] datetime2,
    [DateReglementSemaineMultiple] datetime2,
    [DateReglementPrestation] datetime2,
    [FrequenceEmission] int,
    [ModeEnvoiFacture] int,
    CONSTRAINT [PK_Activite.LotsFacture] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[MouvementsReleveHeures] (
    [Id] uniqueidentifier,
    [ReleveHeuresId] uniqueidentifier,
    [PartieSemaine] nchar(1),
    [TypeMouvementId] nvarchar(128),
    [Lundi] decimal,
    [Mardi] decimal,
    [Mercredi] decimal,
    [Jeudi] decimal,
    [Vendredi] decimal,
    [Samedi] decimal,
    [Dimanche] decimal,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [IsRegularisation] bit,
    CONSTRAINT [PK_Activite.MouvementsReleveHeures] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[ParametragesQualification] (
    [ParametrageSpecificitesId] uniqueidentifier,
    [QualificationCode] nvarchar(20),
    [Renommee] nvarchar(255),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [DetailRisque] varchar(255),
    CONSTRAINT [PK_Activite.ParametragesQualification] PRIMARY KEY CLUSTERED ([ParametrageSpecificitesId], [QualificationCode])
);

CREATE TABLE [Activite].[PerimetresGroupesClients] (
    [Id] int,
    [GroupeParentId] int,
    [DateDebut] datetime2,
    [DateFin] datetime2,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [ClientId] uniqueidentifier,
    [GroupeClientId] int,
    [Discriminator] nvarchar(128),
    CONSTRAINT [PK_Activite.PerimetresGroupesClients] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Activite].[RelevesHeures] (
    [Id] uniqueidentifier,
    [PartieSemaine] nchar(1),
    [ContratId] uniqueidentifier,
    [DateDebut] datetime2,
    [DateFin] datetime2,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [PerimetreDelegationId] int,
    CONSTRAINT [PK_Activite.RelevesHeures] PRIMARY KEY CLUSTERED ([Id], [PartieSemaine])
);

CREATE TABLE [Activite].[Societes] (
    [Id] uniqueidentifier,
    [SIREN] nvarchar(9),
    [RaisonSociale] nvarchar(255),
    [Code] nvarchar(3),
    [Capital] decimal,
    [CodeTvaCee] nvarchar(15),
    [DescriptionGarant] nvarchar(100),
    [Telephone] nvarchar(20),
    [Fax] nvarchar(20),
    [AdresseLigne1] nvarchar(100),
    [AdresseLigne2] nvarchar(100),
    [AdresseLigne3] nvarchar(100),
    [CodePostal] nvarchar(10),
    [Ville] nvarchar(100),
    [PaysCode] nchar(2),
    [CodeAPE] nvarchar(10),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [FormeJuridiqueCode] nvarchar(10),
    [IndicatifTelephone] nvarchar(5),
    [IndicatifFax] nvarchar(5),
    [EtablissementPrincipalId] uniqueidentifier,
    [Etat] int,
    [ComptePaiementVirementId] uniqueidentifier,
    [SocietePaiementVirementId] uniqueidentifier,
    [ComptePaiementChequeId] uniqueidentifier,
    [SocietePaiementChequeId] uniqueidentifier,
    [CompteFacturationId] uniqueidentifier,
    [CommuneId] int,
    CONSTRAINT [PK_Activite.Societes] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Referentiel].[CategoriesSocioProfessionnelles] (
    [Code] nvarchar(10),
    [Description] nvarchar(100),
    [DureeMaxPeriodeEssai] int,
    [MajorationSmic] float,
    [IsActif] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [Niveau] int,
    [IsForfaitJour] bit,
    CONSTRAINT [PK_Referentiel.CategoriesSocioProfessionnelles] PRIMARY KEY CLUSTERED ([Code])
);

CREATE TABLE [Referentiel].[Communes] (
    [CodeDepartement] nchar(3),
    [LibelleEnMajuscules] nvarchar(70),
    [CodePostal] nvarchar(10),
    [Description] nvarchar(70),
    [IsActif] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [Id] int,
    [CodeInsee] nchar(5),
    [CodeInseeParent] nchar(5),
    [LibelleNormalise] nvarchar(70),
    [CodeCollectivite] nvarchar(15),
    CONSTRAINT [PK_Referentiel.Communes] PRIMARY KEY CLUSTERED ([Id])
);

CREATE TABLE [Referentiel].[MotifsContrat] (
    [Code] nvarchar(10),
    [TypeMotif] nvarchar(50),
    [Description] nvarchar(200),
    [IsActif] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [DureeMin] int,
    [DureeMax] int,
    [DureeMaxLM] int,
    [DureeMaxEtranger] int,
    CONSTRAINT [PK_Referentiel.MotifsContrat] PRIMARY KEY CLUSTERED ([Code])
);

CREATE TABLE [Referentiel].[MotifsFinContrat] (
    [Code] nvarchar(10),
    [Description] nvarchar(100),
    [IsActif] bit,
    [CodeLegal] nvarchar(2),
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [CodeMotifFinContratSante] nvarchar(3),
    CONSTRAINT [PK_Referentiel.MotifsFinContrat] PRIMARY KEY CLUSTERED ([Code])
);

CREATE TABLE [Referentiel].[Qualifications] (
    [Code] nvarchar(20),
    [IsARisque] bit,
    [CodeGroupeQualification] nvarchar(5),
    [PCS] nvarchar(10),
    [ComplementPCSCode] nvarchar(10),
    [Description] nvarchar(250),
    [IsActif] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [SecteurDfsCode] nvarchar(20),
    [DetailRisque] varchar(255),
    CONSTRAINT [PK_Referentiel.Qualifications] PRIMARY KEY CLUSTERED ([Code])
);

CREATE TABLE [Referentiel].[Rubriques] (
    [Id] int,
    [IsHeure] bit,
    [IsMajoration] bit,
    [CompteurPaieId] int,
    [CompteurFacturationId] int,
    [RubriqueAssocieeId] int,
    [StatutCode] nchar(1),
    [IsAutoriseePaie] bit,
    [IsAutoriseeFact] bit,
    [CategorieCode] nvarchar(2),
    [TypeRegleGestion] int,
    [PlancherId] int,
    [PlafondId] int,
    [AccumulateurSourceId] int,
    [TauxSalarial] decimal,
    [TauxPatronal] decimal,
    [TauxAbattement] decimal,
    [RubriqueDeblocageId] int,
    [RubriqueAnnulationId] int,
    [RubriqueVersementCetId] int,
    [TauxAcquisitionDroitCode] nvarchar(5),
    [TauxAcquisitionDroit] decimal,
    [IsReserveeAdmin] bit,
    [IsAutoriseeDansFinancier] bit,
    [RubriqueRegulId] int,
    [IsRegul] bit,
    [TypeContratCible] int,
    [Code] nchar(3),
    [Description] nvarchar(250),
    [IsActif] bit,
    [TypeOrganismeCotisation] int,
    [TauxVersementDroitCode] nvarchar(5),
    [TauxVersementDroit] decimal,
    [RubriqueMiseEnAttenteId] int,
    [IsVisiblePaie] bit,
    [IsVisibleFacture] bit,
    [DateCreation] datetime2,
    [DateVersion] datetime2,
    [Createur] nvarchar(100),
    [Modificateur] nvarchar(100),
    [FamilleId] int,
    [TauxPlancherCode] nvarchar(MAX),
    [TypeExercice] int,
    [TypeCalculApprenti] int,
    [IsActivite] bit,
    [MiseEnCet] int,
    CONSTRAINT [PK_Referentiel.Rubriques] PRIMARY KEY CLUSTERED ([Id])
);


ALTER TABLE [Activite].[Agences] ADD CONSTRAINT [FK_Activite.Agences_Activite.DossiersAgence_DossierAgencePrincipalId] FOREIGN KEY ([DossierAgencePrincipalId]) REFERENCES [Activite].[DossiersAgence] ([Id]);

ALTER TABLE [Activite].[AxesAnalytiques] ADD CONSTRAINT [FK_Activite.AxesAnalytiques_Activite.EtablissementsClient_EtablissementId] FOREIGN KEY ([EtablissementClientId]) REFERENCES [Activite].[EtablissementsClient] ([Id]);

ALTER TABLE [Activite].[AxesAnalytiques] ADD CONSTRAINT [FK_Activite.AxesAnalytiques_Activite.Clients_ClientId] FOREIGN KEY ([ClientId]) REFERENCES [Activite].[Clients] ([Id]);


ALTER TABLE [Activite].[Clients] ADD CONSTRAINT [FK_Activite.Clients_Referentiel.Communes_CommuneId] FOREIGN KEY ([CommuneId]) REFERENCES [Referentiel].[Communes] ([Id]);


ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.Agences_AgenceGestionnaireId] FOREIGN KEY ([AgenceGestionnaireId]) REFERENCES [Activite].[Agences] ([Id]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.Agences_AgenceOrigineId] FOREIGN KEY ([AgenceOrigineId]) REFERENCES [Activite].[Agences] ([Id]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.DepartementsEtablissementsClients_DepartementEtablissementClientId] FOREIGN KEY ([DepartementEtablissementClientId]) REFERENCES [Activite].[DepartementsEtablissementsClients] ([Id]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.Clients_ClientIdModelePoste] FOREIGN KEY ([ClientIdModelePoste]) REFERENCES [Activite].[Clients] ([Id]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.DossiersAgence_DossierAgenceId] FOREIGN KEY ([DossierAgenceId]) REFERENCES [Activite].[DossiersAgence] ([Id]);



ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Referentiel.CategoriesSocioProfessionnelles_CategorieCode] FOREIGN KEY ([CategorieCode]) REFERENCES [Referentiel].[CategoriesSocioProfessionnelles] ([Code]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.Interimaires_InterimaireId] FOREIGN KEY ([InterimaireId]) REFERENCES [Activite].[Interimaires] ([Id]);


ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.EtablissementsClient_EtablissementClientId] FOREIGN KEY ([EtablissementClientId]) REFERENCES [Activite].[EtablissementsClient] ([Id]);

ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Activite.EtablissementsClient_EtablissementClientIdModelePoste] FOREIGN KEY ([EtablissementClientIdModelePoste]) REFERENCES [Activite].[EtablissementsClient] ([Id]);




ALTER TABLE [Activite].[ContratsModelesPoste] ADD CONSTRAINT [FK_Activite.ContratsModelesPoste_Referentiel.Qualifications_QualificationCode] FOREIGN KEY ([QualificationCode]) REFERENCES [Referentiel].[Qualifications] ([Code]);

ALTER TABLE [Activite].[DepartementsEtablissementsClients] ADD CONSTRAINT [FK_Activite.DepartementsEtablissementsClients_Activite.EtablissementsClient_EtablissementClientId] FOREIGN KEY ([EtablissementClientId]) REFERENCES [Activite].[EtablissementsClient] ([Id]);

ALTER TABLE [Activite].[DepartementsEtablissementsClients] ADD CONSTRAINT [FK_Activite.DepartementsEtablissementsClients_Referentiel.Communes_CommuneId] FOREIGN KEY ([CommuneId]) REFERENCES [Referentiel].[Communes] ([Id]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Referentiel.Qualifications_QualifCodePersonneRemplacee] FOREIGN KEY ([QualifCodePersonneRemplacee]) REFERENCES [Referentiel].[Qualifications] ([Code]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Referentiel.MotifsContrat_MotifContratCode] FOREIGN KEY ([MotifContratCode]) REFERENCES [Referentiel].[MotifsContrat] ([Code]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Activite.ContratsModelesPoste_ContratId] FOREIGN KEY ([ContratId]) REFERENCES [Activite].[ContratsModelesPoste] ([Id]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Referentiel.CategoriesSocioProfessionnelles_CategorieCodePersonneRemplacee] FOREIGN KEY ([CategorieCodePersonneRemplacee]) REFERENCES [Referentiel].[CategoriesSocioProfessionnelles] ([Code]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Referentiel.MotifsFinContrat_MotifFinContratCode] FOREIGN KEY ([MotifFinContratCode]) REFERENCES [Referentiel].[MotifsFinContrat] ([Code]);

ALTER TABLE [Activite].[DonneesContrat] ADD CONSTRAINT [FK_Activite.DonneesContrat_Referentiel.MotifsFinContrat_MotifFinContratPrevisionnelCode] FOREIGN KEY ([MotifFinContratPrevisionnelCode]) REFERENCES [Referentiel].[MotifsFinContrat] ([Code]);


ALTER TABLE [Activite].[DossierAgenceMatriculeInterimaires] ADD CONSTRAINT [FK_Activite.DossierAgenceMatriculeInterimaires_Activite.DossiersAgence_DossierAgenceId] FOREIGN KEY ([DossierAgenceId]) REFERENCES [Activite].[DossiersAgence] ([Id]);

ALTER TABLE [Activite].[DossiersAgence] ADD CONSTRAINT [FK_Activite.DossiersAgence_Activite.Agences_AgenceId] FOREIGN KEY ([AgenceId]) REFERENCES [Activite].[Agences] ([Id]);

ALTER TABLE [Activite].[DossiersAgence] ADD CONSTRAINT [FK_Activite.DossiersAgence_Activite.Etablissements_EtablissementId] FOREIGN KEY ([EtablissementId]) REFERENCES [Activite].[Etablissements] ([Id]);


ALTER TABLE [Activite].[Etablissements] ADD CONSTRAINT [FK_Activite.Etablissements_Activite.Societes_SocieteId] FOREIGN KEY ([SocieteId]) REFERENCES [Activite].[Societes] ([Id]);

ALTER TABLE [Activite].[Etablissements] ADD CONSTRAINT [FK_Activite.Etablissements_Referentiel.Communes_CommuneId] FOREIGN KEY ([CommuneId]) REFERENCES [Referentiel].[Communes] ([Id]);



ALTER TABLE [Activite].[EtablissementsClient] ADD CONSTRAINT [FK_Activite.EtablissementsClient_Activite.Clients_ClientId] FOREIGN KEY ([ClientId]) REFERENCES [Activite].[Clients] ([Id]);



ALTER TABLE [Activite].[EtablissementsClient] ADD CONSTRAINT [FK_Activite.EtablissementsClient_Referentiel.Communes_CommuneId] FOREIGN KEY ([CommuneId]) REFERENCES [Referentiel].[Communes] ([Id]);


ALTER TABLE [Activite].[EtablissementsClientDossiersAgence] ADD CONSTRAINT [FK_Activite.EtablissementsClientDossiersAgence_Activite.DossiersAgence_DossierAgenceId] FOREIGN KEY ([DossierAgenceId]) REFERENCES [Activite].[DossiersAgence] ([Id]);





ALTER TABLE [Activite].[EtablissementsClientDossiersAgence] ADD CONSTRAINT [FK_Activite.EtablissementsClientDossiersAgence_Activite.EtablissementsClient_EtablissementClientId] FOREIGN KEY ([EtablissementClientId]) REFERENCES [Activite].[EtablissementsClient] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.EtablissementsClient_EtablissementClientId] FOREIGN KEY ([EtablissementClientId]) REFERENCES [Activite].[EtablissementsClient] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.Clients_ClientId] FOREIGN KEY ([ClientId]) REFERENCES [Activite].[Clients] ([Id]);



ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.Etablissements_EtablissementId] FOREIGN KEY ([EtablissementId]) REFERENCES [Activite].[Etablissements] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.DepartementsEtablissementsClients_DepartementClientId] FOREIGN KEY ([DepartementClientId]) REFERENCES [Activite].[DepartementsEtablissementsClients] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.DossiersAgence_SpecialisationDossierAgenceId] FOREIGN KEY ([SpecialisationDossierAgenceId]) REFERENCES [Activite].[DossiersAgence] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.Agences_AgenceId] FOREIGN KEY ([AgenceId]) REFERENCES [Activite].[Agences] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.LotsFacture_LotId] FOREIGN KEY ([LotId]) REFERENCES [Activite].[LotsFacturation] ([Id]);

ALTER TABLE [Activite].[Factures] ADD CONSTRAINT [FK_Activite.Factures_Activite.Factures_IdParent] FOREIGN KEY ([IdParent]) REFERENCES [Activite].[Factures] ([Id]);




ALTER TABLE [Activite].[HorairesEtCouts] ADD CONSTRAINT [FK_Activite.HorairesEtCouts_Activite.AxesAnalytiques_AxeAnalytiqueId] FOREIGN KEY ([AxeAnalytiqueId]) REFERENCES [Activite].[AxesAnalytiques] ([Id]);

ALTER TABLE [Activite].[HorairesEtCouts] ADD CONSTRAINT [FK_Activite.HorairesEtCouts_Activite.ContratsModelesPoste_ContratId] FOREIGN KEY ([ContratId]) REFERENCES [Activite].[ContratsModelesPoste] ([Id]);




ALTER TABLE [Activite].[LieuMission] ADD CONSTRAINT [FK_Activite.LieuMission_Activite.ContratsModelesPoste_ContratId] FOREIGN KEY ([ContratId]) REFERENCES [Activite].[ContratsModelesPoste] ([Id]);


ALTER TABLE [Activite].[LieuMission] ADD CONSTRAINT [FK_Activite.LieuMission_Referentiel.Communes_CommuneIdEnvoiContrat] FOREIGN KEY ([CommuneIdEnvoiContrat]) REFERENCES [Referentiel].[Communes] ([Id]);

ALTER TABLE [Activite].[LieuMission] ADD CONSTRAINT [FK_Activite.LieuMission_Referentiel.Communes_CommuneIdLieuMission] FOREIGN KEY ([CommuneIdLieuMission]) REFERENCES [Referentiel].[Communes] ([Id]);


ALTER TABLE [Activite].[LignesFacture] ADD CONSTRAINT [FK_Activite.LignesFacture_Referentiel.Rubriques_RubriqueId] FOREIGN KEY ([RubriqueId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Activite].[LignesFacture] ADD CONSTRAINT [FK_Activite.LignesFacture_Activite.ContratsModelesPoste_ContratId] FOREIGN KEY ([ContratId]) REFERENCES [Activite].[ContratsModelesPoste] ([Id]);

ALTER TABLE [Activite].[LignesFacture] ADD CONSTRAINT [FK_Activite.LignesFacture_Activite.Factures_FactureId] FOREIGN KEY ([FactureId]) REFERENCES [Activite].[Factures] ([Id]);

ALTER TABLE [Activite].[LignesFacture] ADD CONSTRAINT [FK_Activite.LignesFacture_Activite.LignesReleveHeures_LigneRhId] FOREIGN KEY ([LigneRhId]) REFERENCES [Activite].[LignesReleveHeures] ([Id]);

ALTER TABLE [Activite].[LignesReleveHeures] ADD CONSTRAINT [FK_Activite.LignesReleveHeures_Activite.LotsFacture_LotFactureId] FOREIGN KEY ([LotFactureId]) REFERENCES [Activite].[LotsFacturation] ([Id]);




ALTER TABLE [Activite].[LignesReleveHeures] ADD CONSTRAINT [FK_Activite.LignesReleveHeures_Activite.AxesAnalytiques_AxeAnalytiqueId] FOREIGN KEY ([AxeAnalytiqueId]) REFERENCES [Activite].[AxesAnalytiques] ([Id]);

ALTER TABLE [Activite].[LignesReleveHeures] ADD CONSTRAINT [FK_Activite.LignesReleveHeures_Referentiel.Rubriques_RubriqueId] FOREIGN KEY ([RubriqueId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Activite].[MouvementsReleveHeures] 
ADD CONSTRAINT [FK_Activite.MouvementsReleveHeures_Activite.RelevesHeures] 
FOREIGN KEY ([ReleveHeuresId], [PartieSemaine]) -- On ajoute les deux colonnes
REFERENCES [Activite].[RelevesHeures] ([Id], [PartieSemaine]); -- Correspondance totale

ALTER TABLE [Activite].[ParametragesQualification] ADD CONSTRAINT [FK_Activite.ParametragesQualification_Referentiel.Qualifications_QualificationCode] FOREIGN KEY ([QualificationCode]) REFERENCES [Referentiel].[Qualifications] ([Code]);

ALTER TABLE [Activite].[PerimetresGroupesClients] ADD CONSTRAINT [FK_Activite.PerimetresGroupesClients_Activite.GroupesClients_GroupeParentId] FOREIGN KEY ([GroupeParentId]) REFERENCES [Activite].[GroupesClients] ([Id]);

ALTER TABLE [Activite].[PerimetresGroupesClients] ADD CONSTRAINT [FK_Activite.PerimetresGroupesClients_Activite.GroupesClients_GroupeClientId] FOREIGN KEY ([GroupeClientId]) REFERENCES [Activite].[GroupesClients] ([Id]);

ALTER TABLE [Activite].[PerimetresGroupesClients] ADD CONSTRAINT [FK_Activite.PerimetresGroupesClients_Activite.Clients_ClientId] FOREIGN KEY ([ClientId]) REFERENCES [Activite].[Clients] ([Id]);

ALTER TABLE [Activite].[RelevesHeures] ADD CONSTRAINT [FK_Activite.RelevesHeures_Activite.ContratsModelesPoste_ContratId] FOREIGN KEY ([ContratId]) REFERENCES [Activite].[ContratsModelesPoste] ([Id]);



ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_AccumulateurSourceId] FOREIGN KEY ([AccumulateurSourceId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueAnnulationId] FOREIGN KEY ([RubriqueAnnulationId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueAssocieeId] FOREIGN KEY ([RubriqueAssocieeId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueDeblocageId] FOREIGN KEY ([RubriqueDeblocageId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueMiseEnAttenteId] FOREIGN KEY ([RubriqueMiseEnAttenteId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueRegulId] FOREIGN KEY ([RubriqueRegulId]) REFERENCES [Referentiel].[Rubriques] ([Id]);

ALTER TABLE [Referentiel].[Rubriques] ADD CONSTRAINT [FK_Referentiel.Rubriques_Referentiel.Rubriques_RubriqueVersementCetId] FOREIGN KEY ([RubriqueVersementCetId]) REFERENCES [Referentiel].[Rubriques] ([Id]);



ALTER TABLE [Activite].[Societes] ADD CONSTRAINT [FK_Activite.Societes_Referentiel.Communes_CommuneId] FOREIGN KEY ([CommuneId]) REFERENCES [Referentiel].[Communes] ([Id]);


ALTER TABLE [Activite].[Societes] ADD CONSTRAINT [FK_Activite.Societes_Activite.Etablissements_EtablissementPrincipalId] FOREIGN KEY ([EtablissementPrincipalId]) REFERENCES [Activite].[Etablissements] ([Id]);


