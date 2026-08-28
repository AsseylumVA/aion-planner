const CLASSES = [
  { id: "gladiator", name: "Гладиатор", client: "FIGHTER" },
  { id: "templar", name: "Страж", client: "KNIGHT" },
  { id: "assassin", name: "Убийца", client: "ASSASSIN" },
  { id: "ranger", name: "Стрелок", client: "RANGER" },
  { id: "sorcerer", name: "Волшебник", client: "WIZARD" },
  { id: "spiritmaster", name: "Заклинатель", client: "ELEMENTALLIST" },
  { id: "cleric", name: "Целитель", client: "PRIEST" },
  { id: "chanter", name: "Чародей", client: "CHANTER" },
];

const CLASS_DEFAULTS = {
  gladiator: {
    learned: {
      combat: {F1: "fiFortitude", F2: "waRage", F3: "fiParryFocus", F4: "fiCountBuff", F5: "fiEnergyWing", Digit2: "fiRobustImpulse", Digit3: "fiRaisingImpact", Digit4: "fiShockImpulse", Digit5: "fiDragonSlash", KeyQ: "fiSeismicWave", KeyE: "fiSeismicBillow", KeyR: "fiCounterDrain", KeyF: "waAvengingCrash", KeyA: "fiRobustSmash", KeyD: "waArmorBreak", KeyC: "fiDropImpact", KeyV: "fiCruelBlow", KeyX: "waProvoke", KeyZ: "fiSlashigForce", KeyG: "fiStormBlade", KeyH: "fiWingBlade", F8: "fiBerserk"},
      shift: {KeyQ: "fiDestructBlow", KeyE: "fiFlyingSlash", KeyR: "fiJumpingCut", KeyF: "fiPowerSlash", KeyA: "fiRobustCrash", KeyD: "fiBodySmash", KeyC: "fiForceBlast", KeyV: "waRobustHit", KeyX: "waDash", KeyZ: "fiFighterRage"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  templar: {
    learned: {
      combat: {F1: "knIronBody", F2: "waRage", F3: "knProtectProud", F4: "knPurifyWing", F5: "knStoneBody", Digit2: "knShineSlash", Digit3: "knWindBlade", Digit4: "knShieldSwing", Digit5: "knWindSnatcher", KeyQ: "knSlashDown", KeyE: "knTargetSnatcher", KeyR: "knDivineJudgement", KeyF: "knAbysalJudgement", KeyA: "waAvengingCrash", KeyD: "knFrozingShield", KeyC: "knLegBreak", KeyV: "knWeaponBreak", KeyX: "waArmorBreak", KeyZ: "knAvengingBash", KeyG: "knShineBlade", KeyH: "knBleedingSword", F8: "waShieldStance"},
      shift: {KeyQ: "knJudgement", KeyE: "knDrainSword", KeyR: "knGodJudgement", KeyF: "waProvoke", KeyA: "knBrainBreak", KeyD: "knAvengingBlade", KeyC: "knShieldCharge", KeyV: "waRobustHit", KeyX: "knTurnAggressive", KeyZ: "waDash"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  ranger: {
    learned: {
      combat: {F1: "raQuickSetting", F2: "focusedEvasion", F3: "raRapidBow", F4: "scSpiritofGale", F5: "ritual", Digit2: "raEntangleShot", Digit3: "sudden", Digit4: "raHeavyShot", Digit5: "raTrueShot", KeyQ: "raSteelArrow", KeyE: "raApproachShot", KeyR: "counter", KeyF: "raDrainShot", KeyA: "raFreeShot", KeyD: "raRapidFire", KeyC: "raVenomShot", KeyV: "raCrisisCounter", KeyX: "raBasicShot", KeyZ: "raSpiralArrow", KeyG: "raThroughShot", KeyH: "raAssaultArrow", F8: "returnHome"},
      shift: {KeyQ: "swift", KeyE: "raAimShot", KeyR: "raArrowStorm"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  sorcerer: {
    learned: {
      combat: {F1: "wiPhysicalWall", F2: "wiMindsEye", F3: "wiRapidShield", F4: "maStoneSkin", F5: "wiManaBoost", Digit2: "wiNapalm", Digit3: "wiWizardryHook", Digit4: "wiAbsenceSoul", Digit5: "wiSoulFreeze", KeyQ: "wiDimensionDoor", KeyE: "maGravityCage", KeyR: "wiCrystalMirror", KeyF: "wiMagicalChain", KeyA: "maIceGrab", KeyD: "wiMagicalFlame", KeyC: "wiMagicFist", KeyV: "wiDelayedExplosion", KeyX: "maFlameBolt", KeyZ: "wiFlameLance", KeyG: "wiFireShooter", KeyH: "wiBurningSoul", F8: "returnHome"},
      shift: {KeyQ: "wiMeteor", KeyE: "wiHellFire", KeyR: "wiFlameCage", KeyF: "maRoot", KeyA: "wiFrozenField", KeyD: "wiWindSpear", KeyC: "wiChainBurn", KeyV: "wiSoulEater", KeyX: "wiVitalityDrain", KeyZ: "wiRaisingStorm", KeyG: "wiHydroImpact", KeyB: "wiCursedCorruptTree"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  spiritmaster: {
    learned: {
      combat: {F1: "elResistMagic", F2: "maStoneSkin", F3: "elElementalCall", Digit2: "elDispel", Digit3: "elVacuumExplosion", Digit4: "elDispelExplosion", Digit5: "elFear", KeyQ: "elCursedBreath", KeyE: "elSlow", KeyR: "elEarthGrab", KeyF: "elGaiaGrab", KeyA: "elPetInterupt", KeyD: "elOrderAssail", KeyC: "elPetElementalShock", KeyV: "elPetWideTaunt", KeyX: "elPetElementalWraith", KeyZ: "elEternalShield", KeyG: "elOrderDecaying", KeyH: "elPetElementalTaunt", F8: "returnHome"},
      shift: {KeyQ: "elOrderExplode", KeyE: "maGravityCage", KeyR: "maIceGrab", KeyF: "elAreaCage", KeyA: "maFlameBolt", KeyD: "maRoot", KeyC: "elNightmareRoot", KeyV: "elCountHPMPDrain", KeyX: "elSummonAid", KeyZ: "elMagicalBreakdown", KeyG: "elDespairCurse", KeyB: "elWaterFear"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  cleric: {
    learned: {
      combat: {F1: "prHolyEmpower", F2: "prBlessedShield", F3: "prFocusCasting", F4: "prPrepareHolywar", F5: "prInvinsibleWall", Digit2: "clSmite", Digit3: "prCallResurrection", Digit4: "prHolyExplosion", Digit5: "prRaiseRepentance", KeyQ: "clHallowSwing", KeyE: "prRepentance", KeyR: "prDivineBolt", KeyF: "prAbysalBolt", KeyA: "prPunishingLight", KeyD: "prRoot", KeyC: "prPurify", KeyV: "prCureCondition", KeyX: "clRevive", KeyZ: "prHateDecrease", KeyG: "prAreaResurrection", KeyH: "prDivineSpark", F8: "clBlessofHealth"},
      shift: {KeyQ: "prAngerOfEarth", KeyE: "prCureMind", KeyR: "prMeditation", KeyF: "prInvinsibleVeill", KeyA: "prCircleOfWings", KeyD: "prSkinOfThorn"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [],
      asmo: [],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
  chanter: {
    learned: {
      combat: {F1: "chRenewedVitality", F2: "chParryFocus", F3: "chDemonicWish", F4: "chChantImprovedFly", F5: "chAngelicWish", Digit2: "chPentacleShock", Digit3: "clSmite", Digit4: "chSonicRush", Digit5: "clHallowSwing", KeyQ: "chSonicAssault", KeyE: "chTearingCrash", KeyR: "chLightningStrike", KeyF: "chPressSmash", KeyA: "chTearingStrike", KeyD: "clRevive", KeyC: "chRapidThrust", KeyV: "chSonicGenoside", KeyX: "chViolentSwing", KeyZ: "chParryingStrike", F8: "clBlessofHealth"},
      shift: {KeyQ: "chFrontalAttack", KeyE: "chZest", KeyR: "chCrossParry", KeyF: "chSpaceEscape", KeyA: "chSteelStance"},
      ctrl: {Digit1: "lifeSerum", Digit2: "manaSerum", Digit3: "recoverySerum", Digit4: "curePotion"},
    },
    racial: {
      elyos: [{ layer: "combat", key: "KeyG", skill: "chHolyGloriaElyos" }, { layer: "combat", key: "KeyH", skill: "chMortalStrikeElyos" }],
      asmo: [{ layer: "combat", key: "KeyG", skill: "chAbyssGloriaAsmo" }, { layer: "combat", key: "KeyH", skill: "chBrutalStrikeAsmo" }],
    },
    stigma: {},
    defaultStigmas: { normal: [], greater: [] },
  },
};

