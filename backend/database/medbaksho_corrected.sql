-- ============================================================
-- Mediবাক্স (medbaksho) - Corrected MySQL/MariaDB Database
-- Target: XAMPP MariaDB 10.4+ / MySQL 8.0+
-- Based on the latest ERD and Aritra's database dump.
--
-- WARNING: This script drops and recreates all 19 project tables.
-- Back up any existing data before importing it in phpMyAdmin.
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET SQL_MODE = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

CREATE DATABASE IF NOT EXISTS `medbaksho`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `medbaksho`;

SET @OLD_FOREIGN_KEY_CHECKS = @@FOREIGN_KEY_CHECKS;
SET FOREIGN_KEY_CHECKS = 0;

-- Drop child tables before parent tables so the script can be rerun safely.
DROP TABLE IF EXISTS `prescriptionimage`;
DROP TABLE IF EXISTS `prescriptiontest`;
DROP TABLE IF EXISTS `prescriptionmedicine`;
DROP TABLE IF EXISTS `medicinesubmission`;
DROP TABLE IF EXISTS `prescription`;
DROP TABLE IF EXISTS `medicaltest`;
DROP TABLE IF EXISTS `testcategory`;
DROP TABLE IF EXISTS `medicine`;
DROP TABLE IF EXISTS `medicinetype`;
DROP TABLE IF EXISTS `medicinebrand`;
DROP TABLE IF EXISTS `medicalfacility`;
DROP TABLE IF EXISTS `medicalfacilitytype`;
DROP TABLE IF EXISTS `patientdisease`;
DROP TABLE IF EXISTS `disease`;
DROP TABLE IF EXISTS `doctoravailability`;
DROP TABLE IF EXISTS `doctor`;
DROP TABLE IF EXISTS `patient`;
DROP TABLE IF EXISTS `admin`;
DROP TABLE IF EXISTS `client`;

SET FOREIGN_KEY_CHECKS = @OLD_FOREIGN_KEY_CHECKS;

-- ============================================================
-- 1. CLIENT
-- Renamed from User because USER is easily confused with SQL user/account
-- terminology. user_id is retained for compatibility with the ERD and code.
-- ============================================================
CREATE TABLE `client` (
  `user_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `full_name` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(50) DEFAULT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `account_status` VARCHAR(50) NOT NULL DEFAULT 'Active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_client_email` (`email`),
  KEY `idx_client_account_status` (`account_status`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 2. ADMIN
-- a_id is the table's primary key; user_id is unique to preserve the
-- one-client-to-one-admin-role relationship shown in the ERD.
-- ============================================================
CREATE TABLE `admin` (
  `a_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`a_id`),
  UNIQUE KEY `uq_admin_user_id` (`user_id`),
  CONSTRAINT `fk_admin_client`
    FOREIGN KEY (`user_id`) REFERENCES `client` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 3. PATIENT
-- ============================================================
CREATE TABLE `patient` (
  `p_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `date_of_birth` DATE DEFAULT NULL,
  `blood_group` VARCHAR(10) DEFAULT NULL,
  `address` TEXT DEFAULT NULL,
  PRIMARY KEY (`p_id`),
  UNIQUE KEY `uq_patient_user_id` (`user_id`),
  CONSTRAINT `fk_patient_client`
    FOREIGN KEY (`user_id`) REFERENCES `client` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 4. DOCTOR
-- ============================================================
CREATE TABLE `doctor` (
  `d_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` INT UNSIGNED NOT NULL,
  `licence_number` VARCHAR(255) NOT NULL,
  `degree` VARCHAR(255) DEFAULT NULL,
  `field_of_expertise` VARCHAR(255) DEFAULT NULL,
  `workplace` VARCHAR(255) DEFAULT NULL,
  `verification_status` VARCHAR(50) NOT NULL DEFAULT 'Pending',
  `verified_by_admin_id` INT UNSIGNED DEFAULT NULL,
  `verified_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`d_id`),
  UNIQUE KEY `uq_doctor_user_id` (`user_id`),
  UNIQUE KEY `uq_doctor_licence_number` (`licence_number`),
  KEY `idx_doctor_verification_status` (`verification_status`),
  KEY `idx_doctor_verified_by_admin` (`verified_by_admin_id`),
  CONSTRAINT `fk_doctor_client`
    FOREIGN KEY (`user_id`) REFERENCES `client` (`user_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_doctor_verified_by_admin`
    FOREIGN KEY (`verified_by_admin_id`) REFERENCES `admin` (`a_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 5. DOCTOR AVAILABILITY
-- ============================================================
CREATE TABLE `doctoravailability` (
  `availability_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `doctor_id` INT UNSIGNED NOT NULL,
  `available_date` DATE NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `visiting_fee` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`availability_id`),
  UNIQUE KEY `uq_doctor_availability_slot`
    (`doctor_id`, `available_date`, `start_time`, `end_time`),
  KEY `idx_doctoravailability_date_active`
    (`available_date`, `is_active`),
  CONSTRAINT `chk_doctoravailability_time`
    CHECK (`end_time` > `start_time`),
  CONSTRAINT `chk_doctoravailability_fee`
    CHECK (`visiting_fee` >= 0),
  CONSTRAINT `fk_doctoravailability_doctor`
    FOREIGN KEY (`doctor_id`) REFERENCES `doctor` (`d_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 6. DISEASE
-- ============================================================
CREATE TABLE `disease` (
  `disease_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `disease_name` VARCHAR(255) NOT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`disease_id`),
  UNIQUE KEY `uq_disease_name` (`disease_name`),
  KEY `idx_disease_active` (`is_active`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 7. PATIENT DISEASE
-- ============================================================
CREATE TABLE `patientdisease` (
  `patient_disease_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `patient_id` INT UNSIGNED NOT NULL,
  `disease_id` INT UNSIGNED NOT NULL,
  `diagnosed_date` DATE DEFAULT NULL,
  `current_status` VARCHAR(50) NOT NULL DEFAULT 'Active',
  `custom_disease_name` VARCHAR(255) DEFAULT NULL,
  `notes` TEXT DEFAULT NULL,
  PRIMARY KEY (`patient_disease_id`),
  KEY `idx_patientdisease_patient` (`patient_id`),
  KEY `idx_patientdisease_disease` (`disease_id`),
  KEY `idx_patientdisease_status` (`current_status`),
  CONSTRAINT `fk_patientdisease_patient`
    FOREIGN KEY (`patient_id`) REFERENCES `patient` (`p_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_patientdisease_disease`
    FOREIGN KEY (`disease_id`) REFERENCES `disease` (`disease_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 8. MEDICAL FACILITY TYPE
-- ============================================================
CREATE TABLE `medicalfacilitytype` (
  `facility_type_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `facility_type_name` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`facility_type_id`),
  UNIQUE KEY `uq_medicalfacilitytype_name` (`facility_type_name`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 9. MEDICAL FACILITY
-- ============================================================
CREATE TABLE `medicalfacility` (
  `facility_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `facility_name` VARCHAR(255) NOT NULL,
  `facility_type_id` INT UNSIGNED NOT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`facility_id`),
  UNIQUE KEY `uq_medicalfacility_name_type`
    (`facility_name`, `facility_type_id`),
  KEY `idx_medicalfacility_type` (`facility_type_id`),
  KEY `idx_medicalfacility_active` (`is_active`),
  CONSTRAINT `fk_medicalfacility_type`
    FOREIGN KEY (`facility_type_id`)
    REFERENCES `medicalfacilitytype` (`facility_type_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 10. MEDICINE BRAND
-- ============================================================
CREATE TABLE `medicinebrand` (
  `brand_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `brand_name` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`brand_id`),
  UNIQUE KEY `uq_medicinebrand_name` (`brand_name`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 11. MEDICINE TYPE
-- ============================================================
CREATE TABLE `medicinetype` (
  `med_type_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `med_type_name` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`med_type_id`),
  UNIQUE KEY `uq_medicinetype_name` (`med_type_name`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 12. MEDICINE
-- ============================================================
CREATE TABLE `medicine` (
  `medicine_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `medicine_name` VARCHAR(255) NOT NULL,
  `main_active_ingredient` VARCHAR(255) DEFAULT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  `med_brand_id` INT UNSIGNED NOT NULL,
  `med_type_id` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`medicine_id`),
  UNIQUE KEY `uq_medicine_identity`
    (`medicine_name`, `med_brand_id`, `med_type_id`),
  KEY `idx_medicine_brand` (`med_brand_id`),
  KEY `idx_medicine_type` (`med_type_id`),
  KEY `idx_medicine_active` (`is_active`),
  CONSTRAINT `fk_medicine_brand`
    FOREIGN KEY (`med_brand_id`) REFERENCES `medicinebrand` (`brand_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT `fk_medicine_type`
    FOREIGN KEY (`med_type_id`) REFERENCES `medicinetype` (`med_type_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 13. TEST CATEGORY
-- ============================================================
CREATE TABLE `testcategory` (
  `category_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `category_name` VARCHAR(255) NOT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `uq_testcategory_name` (`category_name`),
  KEY `idx_testcategory_active` (`is_active`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 14. MEDICAL TEST
-- ============================================================
CREATE TABLE `medicaltest` (
  `test_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `category_id` INT UNSIGNED NOT NULL,
  `test_name` VARCHAR(255) NOT NULL,
  `description` TEXT DEFAULT NULL,
  `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (`test_id`),
  UNIQUE KEY `uq_medicaltest_category_name`
    (`category_id`, `test_name`),
  KEY `idx_medicaltest_category` (`category_id`),
  KEY `idx_medicaltest_active` (`is_active`),
  CONSTRAINT `fk_medicaltest_category`
    FOREIGN KEY (`category_id`) REFERENCES `testcategory` (`category_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 15. PRESCRIPTION
-- ============================================================
CREATE TABLE `prescription` (
  `prescription_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `patient_disease_id` INT UNSIGNED NOT NULL,
  `facility_id` INT UNSIGNED DEFAULT NULL,
  `prescription_date` DATE NOT NULL,
  `doctor_name` VARCHAR(255) NOT NULL,
  `custom_facility_name` VARCHAR(255) DEFAULT NULL,
  `illness_location` VARCHAR(255) DEFAULT NULL,
  `advice` TEXT DEFAULT NULL,
  `additional_notes` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`prescription_id`),
  KEY `idx_prescription_patient_disease` (`patient_disease_id`),
  KEY `idx_prescription_facility` (`facility_id`),
  KEY `idx_prescription_date` (`prescription_date`),
  CONSTRAINT `chk_prescription_facility_source`
    CHECK (`facility_id` IS NOT NULL OR `custom_facility_name` IS NOT NULL),
  CONSTRAINT `fk_prescription_patient_disease`
    FOREIGN KEY (`patient_disease_id`)
    REFERENCES `patientdisease` (`patient_disease_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_prescription_facility`
    FOREIGN KEY (`facility_id`) REFERENCES `medicalfacility` (`facility_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 16. PRESCRIPTION MEDICINE
-- ============================================================
CREATE TABLE `prescriptionmedicine` (
  `prescription_id` INT UNSIGNED NOT NULL,
  `medicine_id` INT UNSIGNED NOT NULL,
  `dosage` VARCHAR(255) NOT NULL,
  `times_per_day` INT UNSIGNED NOT NULL,
  `duration_days` INT UNSIGNED NOT NULL,
  `start_date` DATE DEFAULT NULL,
  `end_date` DATE DEFAULT NULL,
  `course_completed` BOOLEAN NOT NULL DEFAULT FALSE,
  `side_effects` TEXT DEFAULT NULL,
  `effectiveness` VARCHAR(255) NOT NULL DEFAULT 'Unknown',
  PRIMARY KEY (`prescription_id`, `medicine_id`),
  KEY `idx_prescriptionmedicine_medicine` (`medicine_id`),
  CONSTRAINT `chk_prescriptionmedicine_times_per_day`
    CHECK (`times_per_day` > 0),
  CONSTRAINT `chk_prescriptionmedicine_duration`
    CHECK (`duration_days` > 0),
  CONSTRAINT `chk_prescriptionmedicine_dates`
    CHECK (`end_date` IS NULL OR `start_date` IS NULL OR `end_date` >= `start_date`),
  CONSTRAINT `fk_prescriptionmedicine_prescription`
    FOREIGN KEY (`prescription_id`)
    REFERENCES `prescription` (`prescription_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_prescriptionmedicine_medicine`
    FOREIGN KEY (`medicine_id`) REFERENCES `medicine` (`medicine_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 17. PRESCRIPTION TEST
-- ============================================================
CREATE TABLE `prescriptiontest` (
  `prescription_id` INT UNSIGNED NOT NULL,
  `test_id` INT UNSIGNED NOT NULL,
  `completion_status` VARCHAR(50) NOT NULL DEFAULT 'Recommended',
  `test_date` DATE DEFAULT NULL,
  `diagnostic_center_name` VARCHAR(255) DEFAULT NULL,
  `result_summary` TEXT DEFAULT NULL,
  `custom_test_name` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`prescription_id`, `test_id`),
  KEY `idx_prescriptiontest_test` (`test_id`),
  KEY `idx_prescriptiontest_status` (`completion_status`),
  CONSTRAINT `fk_prescriptiontest_prescription`
    FOREIGN KEY (`prescription_id`)
    REFERENCES `prescription` (`prescription_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_prescriptiontest_test`
    FOREIGN KEY (`test_id`) REFERENCES `medicaltest` (`test_id`)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 18. PRESCRIPTION IMAGE
-- ============================================================
CREATE TABLE `prescriptionimage` (
  `image_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `prescription_id` INT UNSIGNED NOT NULL,
  `file_path` VARCHAR(500) NOT NULL,
  `file_size_kb` INT UNSIGNED DEFAULT NULL,
  `uploaded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`image_id`),
  UNIQUE KEY `uq_prescriptionimage_path`
    (`prescription_id`, `file_path`),
  KEY `idx_prescriptionimage_prescription` (`prescription_id`),
  CONSTRAINT `fk_prescriptionimage_prescription`
    FOREIGN KEY (`prescription_id`)
    REFERENCES `prescription` (`prescription_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 19. MEDICINE SUBMISSION
-- ============================================================
CREATE TABLE `medicinesubmission` (
  `submission_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `patient_id` INT UNSIGNED NOT NULL,
  `reviewed_by_admin_id` INT UNSIGNED DEFAULT NULL,
  `approved_medicine_id` INT UNSIGNED DEFAULT NULL,
  `proposed_medicine_name` VARCHAR(255) NOT NULL,
  `med_brand_name` VARCHAR(255) DEFAULT NULL,
  `proposed_active_ingredient` VARCHAR(255) DEFAULT NULL,
  `status` VARCHAR(50) NOT NULL DEFAULT 'Pending',
  `submitted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_at` DATETIME DEFAULT NULL,
  `review_comments` TEXT DEFAULT NULL,
  PRIMARY KEY (`submission_id`),
  KEY `idx_medicinesubmission_patient` (`patient_id`),
  KEY `idx_medicinesubmission_admin` (`reviewed_by_admin_id`),
  KEY `idx_medicinesubmission_approved_medicine` (`approved_medicine_id`),
  KEY `idx_medicinesubmission_status_date` (`status`, `submitted_at`),
  CONSTRAINT `chk_medicinesubmission_status`
    CHECK (`status` IN ('Pending', 'Approved', 'Rejected')),
  CONSTRAINT `fk_medicinesubmission_patient`
    FOREIGN KEY (`patient_id`) REFERENCES `patient` (`p_id`)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  CONSTRAINT `fk_medicinesubmission_admin`
    FOREIGN KEY (`reviewed_by_admin_id`) REFERENCES `admin` (`a_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT `fk_medicinesubmission_approved_medicine`
    FOREIGN KEY (`approved_medicine_id`) REFERENCES `medicine` (`medicine_id`)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- End of schema
-- Tables: 19
-- Enforced foreign keys: 21
-- ============================================================
